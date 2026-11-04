"""Stage 6: honest evaluation of the Stage 5 models.

Run from the repo root (after 05_train.py):   python src/06_evaluate.py

What it does
  1. Scores the saved models and the baselines on four sets of scorable rows:
       val_seen    2024, training-area points
       val_unseen  2024, spatial hold-out points (never used in training)
       test_seen   2025, training-area points
       test_unseen 2025, spatial hold-out points
  2. Bootstrap confidence intervals for "how much better than climatology",
     resampling whole points and, separately, whole months (months share weather,
     so resampling points alone is too optimistic).
  3. Error by month.
  4. Feature-group ablations (RF retrained, scored on VAL only).

The test sets are scored here ONCE. Do not change models after looking at them.
Set EVALUATE_TEST = False to stay on validation while you are still tuning.
"""
import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import f1_score

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
SEED, N_BOOT = 42, 500
EVALUATE_TEST = False   # the 2025 test sets were scored on 2026-11-03; keep False from now on
SUF = "" if EVALUATE_TEST else "_valonly"   # val-only runs never overwrite the test results
BASE = ["base_persistence", "base_seasonal_naive", "base_clim"]


def class_from_ndmi(v):
    return np.where(v < 0, 2, np.where(v < 0.2, 1, 0))


def load():
    df = pd.read_csv(ROOT / "data" / "processed" / "features.csv")
    feats = json.loads((ROOT / "data" / "processed" / "feature_list.json").read_text())["features"]
    df = df[(df.lags_complete == 1) & (df.target_valid == 1) & df.target_NDMI.notna()].copy()
    df = df.dropna(subset=BASE)                       # same rows for every method
    return df, feats


def make_sets(df):
    s = {"val_seen": df[(df.split_time == "val") & (df.spatial_holdout == 0)],
         "val_unseen": df[(df.split_time == "val") & (df.spatial_holdout == 1)]}
    if EVALUATE_TEST:
        s["test_seen"] = df[(df.split_time == "test") & (df.spatial_holdout == 0)]
        s["test_unseen"] = df[(df.split_time == "test") & (df.spatial_holdout == 1)]
    return s


def reg_row(y, p):
    e = y - p
    return dict(RMSE=np.sqrt(np.mean(e ** 2)), MAE=np.mean(np.abs(e)),
                R2=1 - (e ** 2).sum() / ((y - y.mean()) ** 2).sum())


def cluster_ci(d, num_m, num_b, key, rng, kind):
    """Bootstrap by cluster. kind='gain': % RMSE reduction; kind='acc': accuracy gain (points)."""
    t = pd.DataFrame({"k": d[key].values, "m": num_m, "b": num_b, "n": 1.0}).groupby("k").sum()
    sm, sb, n = t.m.values, t.b.values, t.n.values
    idx = rng.integers(0, len(t), size=(N_BOOT, len(t)))
    if kind == "gain":
        v = 100 * (1 - np.sqrt(sm[idx].sum(1) / n[idx].sum(1)) / np.sqrt(sb[idx].sum(1) / n[idx].sum(1)))
    else:
        v = 100 * (sm[idx].sum(1) / n[idx].sum(1) - sb[idx].sum(1) / n[idx].sum(1))
    lo, mid, hi = np.percentile(v, [2.5, 50, 97.5])
    return f"{mid:+.1f} [{lo:+.1f}, {hi:+.1f}]  ({len(t)} {key} clusters)"


def main():
    tab = ROOT / "results" / "tables"
    tab.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    df, feats = load()
    sets = make_sets(df)
    md = ROOT / "models"
    rf_r, xgb_r = joblib.load(md / "rf_reg.pkl"), joblib.load(md / "xgb_reg.pkl")
    rf_c, xgb_c = joblib.load(md / "rf_clf.pkl"), joblib.load(md / "xgb_clf.pkl")
    if EVALUATE_TEST:
        print("NOTE: test sets are being scored. Treat these numbers as final.\n")

    # ---------- 1. regression and classification scores ----------
    reg_rows, clf_rows, store = [], [], {}
    for name, d in sets.items():
        X, y = d[feats].values.astype(float), d.target_NDMI.values
        yc = d.target_class_proxy.values.astype(int)
        preds = {b: d[b].values for b in BASE}
        preds["RandomForest"], preds["XGBoost"] = rf_r.predict(X), xgb_r.predict(X)
        base_rmse = reg_row(y, preds["base_clim"])["RMSE"]
        for m, p in preds.items():
            r = reg_row(y, p)
            reg_rows.append(dict(set=name, model=m, n=len(d), **r,
                                 gain_vs_clim_pct=100 * (1 - r["RMSE"] / base_rmse)))
        cpred = {b: class_from_ndmi(d[b].values) for b in BASE}
        cpred["RandomForest"], cpred["XGBoost"] = rf_c.predict(X), xgb_c.predict(X)
        for m, p in cpred.items():
            f1s = f1_score(yc, p, average=None, labels=[0, 1, 2], zero_division=0)
            clf_rows.append(dict(set=name, model=m, n=len(d), Accuracy=np.mean(p == yc),
                                 wF1=f1_score(yc, p, average="weighted", zero_division=0),
                                 F1_Low=f1s[0], F1_Moderate=f1s[1], F1_High=f1s[2]))
        store[name] = (d, y, yc, preds, cpred)
    reg = pd.DataFrame(reg_rows).round(4)
    clf = pd.DataFrame(clf_rows).round(4)
    reg.to_csv(tab / f"stage6{SUF}_regression.csv", index=False)
    clf.to_csv(tab / f"stage6{SUF}_classification.csv", index=False)
    print("REGRESSION (scorable rows only)")
    print(reg.to_string(index=False))
    print("\nCLASSIFICATION (scorable rows only)")
    print(clf.to_string(index=False))

    # ---------- 2. bootstrap confidence intervals ----------
    print("\nHOW MUCH BETTER THAN BASELINES?  median [95% interval]")
    ci_rows = []
    for name, (d, y, yc, preds, cpred) in store.items():
        for model in ("RandomForest", "XGBoost"):
            for key in ("point_id", "target_month", "block_id"):
                g = cluster_ci(d, (y - preds[model]) ** 2, (y - preds["base_clim"]) ** 2, key, rng, "gain")
                a = cluster_ci(d, (cpred[model] == yc).astype(float),
                               (cpred["base_seasonal_naive"] == yc).astype(float), key, rng, "acc")
                ci_rows.append(dict(set=name, model=model, resample=key,
                                    rmse_gain_vs_clim_pct=g, acc_gain_vs_seasonal_naive_pts=a))
    ci = pd.DataFrame(ci_rows)
    ci.to_csv(tab / f"stage6{SUF}_bootstrap_ci.csv", index=False)
    for _, r in ci[ci.model == "RandomForest"].iterrows():
        print(f"  {r['set']:11s} resample {r['resample']:12s} RMSE gain vs clim (%): {r['rmse_gain_vs_clim_pct']}")
        print(f"  {'':11s} {'':20s} accuracy gain vs seasonal naive (pts): {r['acc_gain_vs_seasonal_naive_pts']}")

    # ---------- 3. error by month ----------
    rows = []
    for name, (d, y, yc, preds, cpred) in store.items():
        for mth, idx in d.groupby("target_month").indices.items():
            rows.append(dict(set=name, target_month=mth, n=len(idx),
                             RMSE_RF=np.sqrt(np.mean((y[idx] - preds["RandomForest"][idx]) ** 2)),
                             RMSE_clim=np.sqrt(np.mean((y[idx] - preds["base_clim"][idx]) ** 2)),
                             RMSE_seasonal_naive=np.sqrt(np.mean((y[idx] - preds["base_seasonal_naive"][idx]) ** 2)),
                             mean_n_s2=d.iloc[idx].n_s2.mean() if "n_s2" in d else np.nan))
    bym = pd.DataFrame(rows).round(4)
    bym.to_csv(tab / f"stage6{SUF}_error_by_month.csv", index=False)
    print("\nERROR BY TARGET MONTH (seen points)")
    print(bym[bym.set.str.endswith("_seen")].to_string(index=False))

    # ---------- 4. ablations (validation only) ----------
    train = df[(df.split_time == "train") & (df.spatial_holdout == 0)]
    d, y, *_ = store["val_seen"]
    groups = {
        "rain": [f for f in feats if f.startswith("rain")],
        "optical": [f for f in feats if f.startswith(("NDMI", "NDVI", "NDWI"))],
        "soil": [f for f in feats if f.startswith("soil_moist")],
        "radar": [f for f in feats if f.startswith(("VV", "VH"))],
        "season": ["month_sin", "month_cos"],
        "flags": [f for f in ("optical_valid", "months_since_obs", "n_s2", "low_conf_month", "district_gap")
                  if f in feats],
    }
    configs = {"all features": feats}
    for g, cols in groups.items():
        configs[f"without {g}"] = [f for f in feats if f not in cols]
    configs["rain + season only (no satellite)"] = groups["rain"] + groups["season"]
    configs["optical + season only (no rain/soil/radar)"] = groups["optical"] + groups["season"]
    base_rmse = reg_row(y, d["base_clim"].values)["RMSE"]
    rows = []
    print("\nABLATIONS (RF retrained, scored on val_seen; climatology RMSE = %.4f)" % base_rmse)
    for name, cols in configs.items():
        m = RandomForestRegressor(n_estimators=150, max_features=0.4, min_samples_leaf=5,
                                  n_jobs=-1, random_state=SEED)
        m.fit(train[cols].values.astype(float), train.target_NDMI.values)
        r = reg_row(y, m.predict(d[cols].values.astype(float)))
        rows.append(dict(config=name, n_features=len(cols), RMSE=round(r["RMSE"], 4),
                         R2=round(r["R2"], 4), gain_vs_clim_pct=round(100 * (1 - r["RMSE"] / base_rmse), 1)))
        print(f"  {name:45s} feats {len(cols):2d}  RMSE {r['RMSE']:.4f}  gain vs clim {rows[-1]['gain_vs_clim_pct']:+.1f}%")
    pd.DataFrame(rows).to_csv(tab / f"stage6{SUF}_ablation.csv", index=False)
    print("\n[DONE] Stage 6 evaluation. Tables are in results/tables/stage6_*.csv")


if __name__ == "__main__":
    main()