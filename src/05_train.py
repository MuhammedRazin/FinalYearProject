"""Stage 5: train models and evaluate against baselines.

Run from the repo root (after 04_features.py):   python src/05_train.py

Regression  (predict target_NDMI):  Ridge, Random Forest, XGBoost
Classification (target_class_proxy: 0 Low / 1 Moderate / 2 High stress):
    Random Forest, XGBoost

Evaluation
- Trained ONLY on split_time == "train" AND spatial_holdout == 0   (CHANGED)
- Scored ONLY on val rows with target_valid == 1 and spatial_holdout == 0
- The spatial hold-out points are never used here: they are kept for Stage 6
- Regression baselines: persistence, seasonal_naive, clim
- Classification baselines: the same three, thresholded into classes, plus
  "always predict the most common training class"                  (CHANGED)

Outputs
results/tables/stage5_regression_scores.csv
results/tables/stage5_classification_scores.csv
results/tables/stage5_feature_importance_rf.csv
results/figures/stage5_val_scatter.png
results/figures/stage5_confusion_matrix.png   (best classifier by weighted F1)
models/*.pkl and models/feature_list.json
"""
import json
import sys
import warnings
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRegressor

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path(__file__).resolve().parents[1]
SEED = 42
CLASS_NAMES = ["Low", "Moderate", "High"]
BASELINES = ["base_persistence", "base_seasonal_naive", "base_clim"]


# ── helpers ──────────────────────────────────────────────────────────────────

def load_data():
    feat_path = ROOT / "data" / "processed" / "features.csv"
    meta_path = ROOT / "data" / "processed" / "feature_list.json"
    print(f"Loading {feat_path} ...")
    df = pd.read_csv(feat_path)
    meta = json.loads(meta_path.read_text())
    return df, meta


def class_from_ndmi(v):
    """Same thresholds as target_class_proxy: <0 High(2), 0-0.2 Moderate(1), >=0.2 Low(0)."""
    return np.where(v < 0, 2, np.where(v < 0.2, 1, 0))


def make_splits(df, features):
    """Return X/y arrays for train and scorable-val rows."""
    df = df[df.lags_complete == 1].copy()

    # CHANGED: hold-out points are excluded from training as well as from val
    train = df[(df.split_time == "train") & (df.spatial_holdout == 0)]
    assert (train.spatial_holdout == 0).all()
    val = df[(df.split_time == "val") &
             (df.target_valid == 1) &
             (df.spatial_holdout == 0)]

    X_va = val[features].values.astype(float)
    y_reg_va = val["target_NDMI"].values

    train_reg = train.dropna(subset=["target_NDMI"])
    X_tr = train_reg[features].values.astype(float)
    y_reg_tr = train_reg["target_NDMI"].values

    tr_clf = train.dropna(subset=["target_class_proxy"])
    va_clf = val.dropna(subset=["target_class_proxy"])
    X_tr_clf = tr_clf[features].values.astype(float)
    X_va_clf = va_clf[features].values.astype(float)
    y_clf_tr = tr_clf["target_class_proxy"].values.astype(int)
    y_clf_va = va_clf["target_class_proxy"].values.astype(int)

    return (X_tr, X_va, y_reg_tr, y_reg_va,
            X_tr_clf, X_va_clf, y_clf_tr, y_clf_va,
            train_reg, val, tr_clf, va_clf)


def reg_metrics(y_true, y_pred, label):
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    print(f"  {label:25s}  RMSE {rmse:.4f}  MAE {mae:.4f}  R2 {r2:.4f}")
    return {"model": label, "RMSE": round(rmse, 4),
            "MAE": round(mae, 4), "R2": round(r2, 4)}


def clf_metrics(y_true, y_pred, label):
    acc = accuracy_score(y_true, y_pred)
    f1w = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    f1s = f1_score(y_true, y_pred, average=None, labels=[0, 1, 2], zero_division=0)
    print(f"  {label:25s}  Acc {acc:.4f}  wF1 {f1w:.4f}  "
          f"F1[Low {f1s[0]:.3f}  Mod {f1s[1]:.3f}  High {f1s[2]:.3f}]")
    return {"model": label, "Accuracy": round(acc, 4), "wF1": round(f1w, 4),
            "F1_Low": round(f1s[0], 3), "F1_Moderate": round(f1s[1], 3),
            "F1_High": round(f1s[2], 3)}


# ── regression ────────────────────────────────────────────────────────────────

def train_regression(X_tr, X_va, y_tr, y_va, val_df, models_dir):
    print("\n-- REGRESSION (target_NDMI) ------------------------------------")
    rows = []

    for b in BASELINES:
        mask = val_df[b].notna()
        rows.append(reg_metrics(y_va[mask.values], val_df.loc[mask, b].values, b))

    scaler = StandardScaler()
    X_tr_sc = scaler.fit_transform(X_tr)
    X_va_sc = scaler.transform(X_va)
    ridge = Ridge(alpha=1.0, random_state=SEED)
    ridge.fit(X_tr_sc, y_tr)
    rows.append(reg_metrics(y_va, ridge.predict(X_va_sc), "Ridge"))

    rf = RandomForestRegressor(n_estimators=300, max_features=0.4,
                               min_samples_leaf=5, n_jobs=-1, random_state=SEED)
    rf.fit(X_tr, y_tr)
    rows.append(reg_metrics(y_va, rf.predict(X_va), "RandomForest"))

    # eval_set is only logged: there is no early stopping, so val does not influence fitting
    xgb = XGBRegressor(n_estimators=500, learning_rate=0.05, max_depth=6,
                       subsample=0.8, colsample_bytree=0.6, n_jobs=-1,
                       random_state=SEED, verbosity=0)
    xgb.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
    rows.append(reg_metrics(y_va, xgb.predict(X_va), "XGBoost"))

    joblib.dump((ridge, scaler), models_dir / "ridge.pkl")
    joblib.dump(rf, models_dir / "rf_reg.pkl")
    joblib.dump(xgb, models_dir / "xgb_reg.pkl")
    print("  Models saved.")
    return rows, ridge, scaler, rf, xgb


# ── classification ────────────────────────────────────────────────────────────

def train_classification(X_tr, X_va, y_tr, y_va, val_df, models_dir):
    print("\n-- CLASSIFICATION (target_class_proxy) --------------------------")
    rows = []

    # CHANGED: baselines so the accuracy numbers can be interpreted
    for b in BASELINES:
        mask = val_df[b].notna().values
        pred = class_from_ndmi(val_df.loc[mask, b].values)
        rows.append(clf_metrics(y_va[mask], pred, b))
    majority = np.bincount(y_tr).argmax()
    rows.append(clf_metrics(y_va, np.full_like(y_va, majority), "base_majority_class"))

    rf_clf = RandomForestClassifier(n_estimators=300, max_features=0.4,
                                    min_samples_leaf=5, n_jobs=-1, random_state=SEED)
    rf_clf.fit(X_tr, y_tr)
    rows.append(clf_metrics(y_va, rf_clf.predict(X_va), "RandomForest"))

    xgb_clf = XGBClassifier(n_estimators=500, learning_rate=0.05, max_depth=6,
                            subsample=0.8, colsample_bytree=0.6, n_jobs=-1,
                            random_state=SEED, verbosity=0, eval_metric="mlogloss")
    xgb_clf.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
    rows.append(clf_metrics(y_va, xgb_clf.predict(X_va), "XGBoost"))

    joblib.dump(rf_clf, models_dir / "rf_clf.pkl")
    joblib.dump(xgb_clf, models_dir / "xgb_clf.pkl")
    print("  Models saved.")
    return rows, rf_clf, xgb_clf


# ── plots ─────────────────────────────────────────────────────────────────────

def plot_scatter(y_va, preds_dict, out_path):
    models = [k for k in preds_dict if k not in BASELINES]
    fig, axes = plt.subplots(1, len(models), figsize=(5 * len(models), 4.5), sharey=True)
    lims = (float(np.nanmin(y_va)) - 0.05, float(np.nanmax(y_va)) + 0.05)
    for ax, name in zip(axes, models):
        y_pred = preds_dict[name]
        ax.scatter(y_va, y_pred, s=6, alpha=0.3, color="#4a90d9")
        ax.plot(lims, lims, "r--", lw=1)
        ax.set_title(f"{name}\nRMSE={np.sqrt(mean_squared_error(y_va, y_pred)):.4f}")
        ax.set_xlabel("Actual NDMI")
        ax.set_xlim(lims)
        ax.set_ylim(lims)
    axes[0].set_ylabel("Predicted NDMI")
    fig.suptitle("Val set: predicted vs actual NDMI (scorable rows, no hold-out)", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Scatter plot saved -> {out_path}")


def plot_confusion(y_va, y_pred, model_name, out_path):
    cm = confusion_matrix(y_va, y_pred, labels=[0, 1, 2])
    fig, ax = plt.subplots(figsize=(5, 4))
    ConfusionMatrixDisplay(cm, display_labels=CLASS_NAMES).plot(ax=ax, colorbar=False, cmap="Blues")
    ax.set_title(f"Confusion matrix - {model_name}\n(val, scorable, no hold-out)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Confusion matrix saved -> {out_path}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    df, meta = load_data()
    features = meta["features"]

    (X_tr, X_va, y_reg_tr, y_reg_va,
     X_tr_clf, X_va_clf, y_clf_tr, y_clf_va,
     train_df, val_df, tr_clf_df, va_clf_df) = make_splits(df, features)

    print(f"\nTrain rows : {len(X_tr):,} ({train_df.point_id.nunique()} points, hold-out excluded)")
    print(f"Val scorable rows : {len(X_va):,}")
    print(f"Clf train  : {len(X_tr_clf):,}  |  Clf val scorable  : {len(X_va_clf):,}")
    print(f"Features   : {len(features)}")

    models_dir = ROOT / "models"
    models_dir.mkdir(exist_ok=True)

    reg_rows, ridge, scaler, rf_reg, xgb_reg = train_regression(
        X_tr, X_va, y_reg_tr, y_reg_va, val_df, models_dir)
    clf_rows, rf_clf, xgb_clf = train_classification(
        X_tr_clf, X_va_clf, y_clf_tr, y_clf_va, va_clf_df, models_dir)

    tab = ROOT / "results" / "tables"
    tab.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(reg_rows).to_csv(tab / "stage5_regression_scores.csv", index=False)
    pd.DataFrame(clf_rows).to_csv(tab / "stage5_classification_scores.csv", index=False)
    print(f"\n  Scores saved in {tab}")

    (models_dir / "feature_list.json").write_text(json.dumps({"features": features}, indent=2))

    fig_dir = ROOT / "results" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    preds = {
        "base_persistence": val_df["base_persistence"].values,
        "base_seasonal_naive": val_df["base_seasonal_naive"].values,
        "base_clim": val_df["base_clim"].values,
        "Ridge": ridge.predict(scaler.transform(X_va)),
        "RandomForest": rf_reg.predict(X_va),
        "XGBoost": xgb_reg.predict(X_va),
    }
    plot_scatter(y_reg_va, preds, fig_dir / "stage5_val_scatter.png")

    # CHANGED: plot whichever classifier has the higher weighted F1 (was always XGBoost)
    wf1 = {r["model"]: r["wF1"] for r in clf_rows if r["model"] in ("RandomForest", "XGBoost")}
    best = max(wf1, key=wf1.get)
    best_model = rf_clf if best == "RandomForest" else xgb_clf
    plot_confusion(y_clf_va, best_model.predict(X_va_clf), best,
                   fig_dir / "stage5_confusion_matrix.png")

    imp = pd.Series(rf_reg.feature_importances_, index=features).sort_values(ascending=False)
    imp.rename("importance").rename_axis("feature").reset_index().to_csv(
        tab / "stage5_feature_importance_rf.csv", index=False)
    print("\nTop-10 features (RF regressor, impurity importance):")
    print(imp.head(10).to_string())

    print("\n[DONE] Stage 5 complete.")


if __name__ == "__main__":
    main()