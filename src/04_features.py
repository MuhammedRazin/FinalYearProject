"""Stage 4: feature table, next-month target, baseline columns, splits, leakage checks.

Run from the repo root (after 03_gap_handling.py):   python src/04_features.py

One row = one point at month t. Features use data up to and including month t.
The target is the REAL (unfilled) NDMI at month t+1.

Splits (by target month):  train <= 2023, val = 2024, test = 2025.
Spatial hold-out: ~20% of 0.1-degree blocks, never used for training.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TRAIN_END, VAL_YEAR, TEST_YEAR = 2023, 2024, 2025
BLOCK_DEG = 0.1
HOLDOUT_FRAC = 0.20
SEED = 42
LAGS = (1, 2, 3)
LAG_COLS = ["NDMI_fill", "NDVI_fill", "NDWI_fill", "rain_mm", "soil_moist", "VV", "VH"]
CUR_COLS = ["NDVI_fill", "NDWI_fill", "NDMI_fill", "optical_valid", "months_since_obs",
            "n_s2", "low_conf_month", "district_gap", "rain_mm", "soil_moist", "VV", "VH"]


def build(df):
    """Build features, targets and baselines. Uses only past data for features."""
    df = df.sort_values(["point_id", "year", "month"]).reset_index(drop=True)
    g = df.groupby("point_id")
    f = df[["point_id", "lon", "lat", "year", "month"]].copy()
    f["t_index"] = g.cumcount()

    # --- features at time t ---
    for c in CUR_COLS:
        f[c] = df[c]
    for c in LAG_COLS:
        for k in LAGS:
            f[f"{c}_lag{k}"] = g[c].shift(k)
    f["rain_sum2"] = f.rain_mm + f.rain_mm_lag1
    f["rain_sum3"] = f.rain_sum2 + f.rain_mm_lag2
    f["NDMI_diff1"] = f.NDMI_fill - f.NDMI_fill_lag1
    f["month_sin"] = np.sin(2 * np.pi * f.month / 12)
    f["month_cos"] = np.cos(2 * np.pi * f.month / 12)
    f["lags_complete"] = (f.t_index >= max(LAGS)).astype(int)

    # --- targets: the REAL observation one month ahead ---
    f["target_year"] = g.year.shift(-1)
    f["target_month"] = g.month.shift(-1)
    f["target_NDMI"] = g.NDMI.shift(-1)
    f["target_valid"] = (g.optical_valid.shift(-1) == 1).astype(int)
    f["target_low_conf"] = g.low_conf_month.shift(-1)
    f["target_delta"] = f.target_NDMI - f.NDMI_fill
    cls = np.where(f.target_NDMI < 0, 2, np.where(f.target_NDMI < 0.2, 1, 0))  # 0 Low,1 Mod,2 High
    f["target_class_proxy"] = np.where(f.target_NDMI.notna(), cls, np.nan)
    f = f[f.target_year.notna()].copy()           # last month has no next month
    f["target_year"] = f.target_year.astype(int)
    f["target_month"] = f.target_month.astype(int)

    # --- baseline predictions for the target month ---
    f["base_persistence"] = f.NDMI_fill
    f["base_seasonal_naive"] = g.NDMI_fill.shift(11).reindex(f.index)   # same month last year
    clim = (df[df.year <= TRAIN_END].groupby(["point_id", "month"]).NDMI.mean().rename("base_clim"))
    f = f.merge(clim, left_on=["point_id", "target_month"], right_index=True, how="left")
    month_mean = clim.groupby("month").mean()
    f["base_clim"] = f.base_clim.fillna(f.target_month.map(month_mean))
    return f


def add_splits(f):
    f["split_time"] = np.select([f.target_year <= TRAIN_END, f.target_year == VAL_YEAR,
                                 f.target_year == TEST_YEAR], ["train", "val", "test"], "other")
    blocks = (np.floor(f.lon / BLOCK_DEG).astype(int).astype(str) + "_" +
              np.floor(f.lat / BLOCK_DEG).astype(int).astype(str))
    f["block_id"] = blocks
    ids = np.sort(blocks.unique())
    rng = np.random.default_rng(SEED)
    hold = set(rng.choice(ids, size=max(1, int(round(HOLDOUT_FRAC * len(ids)))), replace=False))
    f["spatial_holdout"] = blocks.isin(hold).astype(int)
    return f


FEATURES = (CUR_COLS + [f"{c}_lag{k}" for c in LAG_COLS for k in LAGS] +
            ["rain_sum2", "rain_sum3", "NDMI_diff1", "month_sin", "month_cos"])
TARGETS = ["target_NDMI", "target_delta", "target_class_proxy"]
BASELINES = ["base_persistence", "base_seasonal_naive", "base_clim"]


# ---------- leakage checks ----------
def check(df, f):
    print("\nLEAKAGE AND ALIGNMENT CHECKS")
    # 1. target is exactly the next month
    gap = (f.target_year * 12 + f.target_month) - (f.year * 12 + f.month)
    assert (gap == 1).all(), "target is not exactly one month ahead"
    print("  [PASS] target month = feature month + 1 for every row")

    look = df.set_index(["point_id", "year", "month"])
    s = f.sample(3000, random_state=0)
    idx = pd.MultiIndex.from_arrays([s.point_id, s.target_year, s.target_month])
    assert np.allclose(s.target_NDMI.values, look.NDMI.reindex(idx).values, equal_nan=True)
    print("  [PASS] target_NDMI equals the raw NDMI of the next month (3000 random rows)")

    # 2. lags point to the past
    for k in LAGS:
        s = f[f.t_index >= k].sample(3000, random_state=k)
        mi = s.year * 12 + s.month - 1 - k
        idx = pd.MultiIndex.from_arrays([s.point_id, mi // 12, mi % 12 + 1])
        assert np.allclose(s[f"NDMI_fill_lag{k}"].values, look.NDMI_fill.reindex(idx).values)
    print("  [PASS] lag1-3 values equal the filled NDMI 1-3 months earlier")

    # 3. targets are not among the features
    assert not set(FEATURES) & set(TARGETS + ["target_valid", "target_year", "target_month"])
    assert not any(c.startswith("target") for c in FEATURES)
    print("  [PASS] no target column is used as a feature")

    # 4. causality: changing the future must not change features of the past
    cut = pd.Timestamp("2024-06-01")
    cut_mi = cut.year * 12 + cut.month - 1
    d2 = df.copy()
    future = (d2.year * 12 + d2.month - 1) > cut_mi
    rng = np.random.default_rng(1)
    for c in set(LAG_COLS + ["NDMI", "optical_valid", "n_s2", "months_since_obs",
                              "low_conf_month", "district_gap"]):
        d2[c] = d2[c].astype(float)
        d2.loc[future, c] = rng.normal(size=int(future.sum()))
    f2 = build(d2)
    past = (f.year * 12 + f.month - 1 <= cut_mi)
    a = f[past].sort_values(["point_id", "t_index"])
    b = f2[(f2.year * 12 + f2.month - 1 <= cut_mi)].sort_values(["point_id", "t_index"])
    cols = FEATURES + ["base_persistence", "base_seasonal_naive", "base_clim"]
    assert np.allclose(a[cols].values.astype(float), b[cols].values.astype(float), equal_nan=True)
    print(f"  [PASS] features and baselines for months <= {cut:%Y-%m} are unchanged "
          "when later data is scrambled")

    # 5. splits
    tr = f[f.split_time == "train"]
    va = f[f.split_time == "val"]
    te = f[f.split_time == "test"]
    assert tr.target_year.max() < va.target_year.min() <= va.target_year.max() < te.target_year.min()
    print("  [PASS] train < val < test in target time, no overlap")
    hold_blocks = set(f[f.spatial_holdout == 1].block_id)
    assert not hold_blocks & set(f[f.spatial_holdout == 0].block_id)
    print(f"  [PASS] hold-out blocks never overlap training blocks "
          f"({len(hold_blocks)} blocks, {f[f.spatial_holdout == 1].point_id.nunique()} points)")


def main():
    src = ROOT / "data" / "processed" / "monthly_filled.csv"
    df = pd.read_csv(src)
    n_pts = df.point_id.nunique()
    n_t = len(df) // n_pts
    f = add_splits(build(df))
    assert len(f) == n_pts * (n_t - 1)
    check(df, f)

    out = ROOT / "data" / "processed" / "features.csv"
    f.to_csv(out, index=False)
    meta = {"features": FEATURES, "targets": TARGETS, "baselines": BASELINES,
            "id_cols": ["point_id", "year", "month", "target_year", "target_month"],
            "flags": ["target_valid", "target_low_conf", "lags_complete",
                      "split_time", "spatial_holdout", "block_id"],
            "not_used_as_features_by_default": ["lon", "lat"]}
    (ROOT / "data" / "processed" / "feature_list.json").write_text(json.dumps(meta, indent=2))

    summ = (f.groupby(["split_time", "spatial_holdout"])
              .agg(rows=("point_id", "size"), points=("point_id", "nunique"),
                   scorable=("target_valid", "sum")).reset_index())
    tab = ROOT / "results" / "tables"
    tab.mkdir(parents=True, exist_ok=True)
    summ.to_csv(tab / "feature_table_summary.csv", index=False)
    print("\nSaved", out, f.shape)
    print("\nRows per split (scorable = target is a real observation):")
    print(summ.to_string(index=False))
    print("\nProxy class mix among scorable rows (0 Low, 1 Moderate, 2 High stress):")
    sc = f[f.target_valid == 1]
    print(sc.groupby("split_time").target_class_proxy.value_counts(normalize=True)
            .unstack().round(3).to_string())
    print("\nSimple baseline RMSE on scorable VAL rows (real targets only):")
    v = sc[sc.split_time == "val"]
    for b in BASELINES:
        m = v[b].notna()
        print(f"  {b:20s} RMSE {np.sqrt(((v.loc[m, b] - v.loc[m, 'target_NDMI']) ** 2).mean()):.4f}"
              f"   rows {int(m.sum())}")


if __name__ == "__main__":
    main()