"""Stage 7: rolling-origin evaluation and two diagnostics.

Run from the repo root (after 06_evaluate.py):   python src/07_rolling_origin.py
Takes roughly 10-25 minutes (5 folds x 3 models).

1. ROLLING ORIGIN. For each test year Y in 2021..2025: train on rows whose target month
   is before year Y (hold-out points excluded), score on year Y, and recompute the
   climatology baseline from years before Y only. Five test years show how stable the
   gain over climatology is, instead of relying on 2024 and 2025 alone.
2. DIAGNOSTIC A. Do the model's errors line up with next-month rainfall anomalies?
   (The features at month t cannot see rainfall in month t+1.)
3. DIAGNOSTIC B. "Oracle" model that is GIVEN next month's rainfall. It shows how much
   skill is limited by not knowing future weather. It cannot be deployed: report it only
   as an upper bound.

Known limitation: the gap-filled INPUT values (Stage 3) use a climatology built from years
<= 2023, so for folds 2021-2023 the filled inputs contain a little same-year information.
The table therefore also reports the gain on rows whose current-month input is a REAL
observation (optical_valid == 1), where this matters least.

"blend_RF_clim" (50/50 average) is EXPLORATORY: it was added after seeing Stage 6 results.
"""
import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
SEED, N_BOOT = 42, 1000
FOLDS = (2021, 2022, 2023, 2024, 2025)
MODELS = ["RandomForest", "XGBoost", "blend_RF_clim", "RF_oracle_next_rain"]
COLS = ["persistence", "seasonal_naive", "climatology"] + MODELS
MIN_MONTH_ROWS = 200       # months with fewer scorable rows are ignored in diagnostic A


def cls(v):
    return np.where(v < 0, 2, np.where(v < 0.2, 1, 0))


def rmse(e):
    return float(np.sqrt(np.mean(np.square(e))))


def load():
    P = ROOT / "data" / "processed"
    feat = pd.read_csv(P / "features.csv")
    feats = json.loads((P / "feature_list.json").read_text())["features"]
    pro = pd.read_csv(P / "monthly_filled.csv", usecols=["point_id", "year", "month", "rain_mm", "NDMI"])
    nxt = (pro[["point_id", "year", "month", "rain_mm"]]
           .rename(columns={"year": "target_year", "month": "target_month", "rain_mm": "rain_next"}))
    d = feat[feat.lags_complete == 1].merge(nxt, on=["point_id", "target_year", "target_month"], how="left")
    return d, feats, pro


def fit_rf(X, y):
    return RandomForestRegressor(n_estimators=200, max_features=0.4, min_samples_leaf=5,
                                 n_jobs=-1, random_state=SEED).fit(X, y)


def fit_xgb(X, y):
    return XGBRegressor(n_estimators=500, learning_rate=0.05, max_depth=6, subsample=0.8,
                        colsample_bytree=0.6, n_jobs=-1, random_state=SEED, verbosity=0).fit(X, y)


def run_fold(d, feats, pro, Y):
    # climatology from years before Y only (real observations, before gap-month masking)
    h = pro[pro.year < Y]
    c = (h.groupby(["point_id", "month"]).NDMI.mean().rename("climatology").reset_index()
          .rename(columns={"month": "target_month"}))
    month_mean = h.groupby("month").NDMI.mean()
    rain_clim = h.groupby("month").rain_mm.mean()

    tr = d[(d.target_year < Y) & (d.spatial_holdout == 0)].dropna(subset=["target_NDMI", "rain_next"])
    te = d[(d.target_year == Y) & (d.target_valid == 1) & d.target_NDMI.notna()].merge(
        c, on=["point_id", "target_month"], how="left")
    te["climatology"] = te.climatology.fillna(te.target_month.map(month_mean))
    te = te.dropna(subset=["base_persistence", "base_seasonal_naive", "climatology", "rain_next"]).copy()

    Xtr, ytr, Xte = tr[feats].values.astype(float), tr.target_NDMI.values, te[feats].values.astype(float)
    out = pd.DataFrame({"fold": Y, "point_id": te.point_id.values, "block_id": te.block_id.values,
                        "holdout": te.spatial_holdout.values,
                        "ym": (te.target_year * 100 + te.target_month).values,
                        "y": te.target_NDMI.values, "real_input": te.optical_valid.values,
                        "rain_anom": (te.rain_next - te.target_month.map(rain_clim)).values,
                        "persistence": te.base_persistence.values,
                        "seasonal_naive": te.base_seasonal_naive.values,
                        "climatology": te.climatology.values})
    out["RandomForest"] = fit_rf(Xtr, ytr).predict(Xte)
    out["XGBoost"] = fit_xgb(Xtr, ytr).predict(Xte)
    out["blend_RF_clim"] = 0.5 * out.RandomForest + 0.5 * out.climatology
    f2 = feats + ["rain_next"]
    out["RF_oracle_next_rain"] = fit_rf(tr[f2].values.astype(float), ytr).predict(te[f2].values.astype(float))
    print(f"  fold {Y}: trained on {len(tr):,} rows, scored {len(te):,} rows")
    return out


def cluster_gain(df, col, key, rng):
    t = pd.DataFrame({"k": df[key].values, "m": (df.y - df[col]).values ** 2,
                      "b": (df.y - df.climatology).values ** 2, "n": 1.0}).groupby("k").sum()
    idx = rng.integers(0, len(t), size=(N_BOOT, len(t)))
    sm, sb, n = t.m.values, t.b.values, t.n.values
    v = 100 * (1 - np.sqrt(sm[idx].sum(1) / n[idx].sum(1)) / np.sqrt(sb[idx].sum(1) / n[idx].sum(1)))
    lo, mid, hi = np.percentile(v, [2.5, 50, 97.5])
    return f"{mid:+.1f} [{lo:+.1f}, {hi:+.1f}]  ({len(t)} {key} clusters)"


def main():
    tab = ROOT / "results" / "tables"
    fig = ROOT / "results" / "figures"
    tab.mkdir(parents=True, exist_ok=True)
    fig.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    d, feats, pro = load()
    print("ROLLING-ORIGIN FOLDS")
    res = pd.concat([run_fold(d, feats, pro, Y) for Y in FOLDS], ignore_index=True)
    seen, unseen = res[res.holdout == 0], res[res.holdout == 1]

    # ---------- per-fold table (seen points) ----------
    rows = []
    for Y, g in seen.groupby("fold"):
        r = {"fold": Y, "n": len(g)}
        for c in COLS:
            r[f"RMSE_{c}"] = rmse(g.y - g[c])
        for c in MODELS:
            r[f"gain_{c}_%"] = 100 * (1 - r[f"RMSE_{c}"] / r["RMSE_climatology"])
        ym = g.groupby("ym").apply(lambda x: rmse(x.y - x.RandomForest) < rmse(x.y - x.climatology))
        r["RF_better_months"] = f"{int(ym.sum())}/{len(ym)}"
        for c in ["persistence", "seasonal_naive", "climatology", "RandomForest", "blend_RF_clim"]:
            r[f"acc_{c}"] = float(np.mean(cls(g[c].values) == cls(g.y.values)))
        gi = g[g.real_input == 1]
        r["gain_RF_realinput_%"] = 100 * (1 - rmse(gi.y - gi.RandomForest) / rmse(gi.y - gi.climatology))
        rows.append(r)
    fold = pd.DataFrame(rows)
    fold.round(4).to_csv(tab / "stage7_rolling_origin.csv", index=False)
    pd.set_option("display.width", 250)
    print("\nRMSE BY TEST YEAR (seen points, scorable rows)")
    print(fold[["fold", "n"] + [f"RMSE_{c}" for c in COLS]].round(4).to_string(index=False))
    print("\nGAIN VS CLIMATOLOGY (%, positive = better than climatology)")
    print(fold[["fold"] + [f"gain_{c}_%" for c in MODELS] + ["gain_RF_realinput_%", "RF_better_months"]]
          .round(1).to_string(index=False))
    print("\nCLASS ACCURACY (thresholded predictions)")
    print(fold[["fold"] + [c for c in fold.columns if c.startswith("acc_")]].round(3).to_string(index=False))

    # ---------- pooled intervals ----------
    print("\nPOOLED OVER ALL FOLDS: RMSE gain vs climatology (%), median [95% interval]")
    ci = []
    for name, df in (("seen", seen), ("unseen", unseen)):
        for c in ("RandomForest", "XGBoost", "blend_RF_clim", "RF_oracle_next_rain"):
            for key in ("ym", "block_id"):
                s = cluster_gain(df, c, key, rng)
                ci.append(dict(points=name, model=c, resample=key, gain_pct=s))
                print(f"  {name:6s} {c:22s} resample {key:9s}: {s}")
    pd.DataFrame(ci).to_csv(tab / "stage7_pooled_ci.csv", index=False)

    # ---------- diagnostic A: errors vs next-month rainfall anomaly ----------
    g = seen.groupby("ym").apply(lambda x: pd.Series({
        "n": len(x), "rain_anom_mm": x.rain_anom.mean(),
        "RF_bias": (x.RandomForest - x.y).mean(), "clim_bias": (x.climatology - x.y).mean(),
        "RMSE_RF": rmse(x.y - x.RandomForest), "RMSE_clim": rmse(x.y - x.climatology),
        "RMSE_oracle": rmse(x.y - x.RF_oracle_next_rain)})).reset_index()
    g = g[g.n >= MIN_MONTH_ROWS].copy()
    g["RF_minus_clim"] = g.RMSE_RF - g.RMSE_clim
    g.round(4).to_csv(tab / "stage7_rain_diagnostic.csv", index=False)
    print(f"\nDIAGNOSTIC A: {len(g)} year-months with >= {MIN_MONTH_ROWS} scorable rows")
    print("  correlation of RF bias (pred - actual) with next-month rain anomaly: "
          f"Pearson {g.RF_bias.corr(g.rain_anom_mm):+.2f}, Spearman {g.RF_bias.corr(g.rain_anom_mm, method='spearman'):+.2f}")
    print("  correlation of climatology bias with next-month rain anomaly:       "
          f"Pearson {g.clim_bias.corr(g.rain_anom_mm):+.2f}, Spearman {g.clim_bias.corr(g.rain_anom_mm, method='spearman'):+.2f}")
    print("  correlation of (RF RMSE - clim RMSE) with |rain anomaly|:           "
          f"Pearson {g.RF_minus_clim.corr(g.rain_anom_mm.abs()):+.2f}, Spearman {g.RF_minus_clim.corr(g.rain_anom_mm.abs(), method='spearman'):+.2f}")
    print("  (strongly negative bias correlation = wetter-than-normal months are under-predicted)")
    print("\n  Ten months where RF is worst relative to climatology:")
    print(g.sort_values("RF_minus_clim", ascending=False).head(10)
           [["ym", "n", "rain_anom_mm", "RF_bias", "RMSE_RF", "RMSE_clim", "RMSE_oracle"]].round(3).to_string(index=False))

    # ---------- figures ----------
    f1, ax = plt.subplots(figsize=(10, 4.5))
    w = 0.2
    xs = np.arange(len(fold))
    for i, (c, lab) in enumerate([("climatology", "Climatology"), ("RandomForest", "Random Forest"),
                                  ("blend_RF_clim", "Blend (exploratory)"),
                                  ("RF_oracle_next_rain", "Oracle (knows next-month rain)")]):
        ax.bar(xs + (i - 1.5) * w, fold[f"RMSE_{c}"], w, label=lab)
    ax.set_xticks(xs, fold.fold)
    ax.set_xlabel("test year (trained on earlier years only)")
    ax.set_ylabel("RMSE of next-month NDMI")
    ax.set_title("Rolling-origin evaluation (seen points)")
    ax.legend(fontsize=8)
    f1.tight_layout()
    f1.savefig(fig / "stage7_rolling_origin.png", dpi=200)
    plt.close(f1)

    f2, ax = plt.subplots(figsize=(6.5, 5))
    ax.scatter(g.rain_anom_mm, g.RF_bias, s=18, alpha=0.7)
    for _, r in g.sort_values("RF_minus_clim", ascending=False).head(5).iterrows():
        ax.annotate(str(int(r.ym)), (r.rain_anom_mm, r.RF_bias), fontsize=7)
    ax.axhline(0, color="grey", lw=0.6)
    ax.axvline(0, color="grey", lw=0.6)
    ax.set_xlabel("next-month rainfall anomaly (mm)")
    ax.set_ylabel("mean RF error (predicted - actual NDMI)")
    ax.set_title("Do errors track next month's rain?")
    f2.tight_layout()
    f2.savefig(fig / "stage7_rain_bias.png", dpi=200)
    plt.close(f2)
    print("\n[DONE] tables: results/tables/stage7_*.csv   figures: results/figures/stage7_*.png")
    print("REMINDER: the oracle uses true next-month rain. It is an upper bound, not a usable model.")


if __name__ == "__main__":
    main()
