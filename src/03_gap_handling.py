"""Stage 3: gap handling for the Kannur monthly GEE export.

Run from the repo root:   python src/03_gap_handling.py

What it does
  1. Cleans extreme optical values and treats near-empty months as missing.
  2. Fills soil moisture for permanently masked points (nearest valid point).
  3. Fills short radar gaps (causal forward-fill).
  4. Compares three CAUSAL fill methods for NDMI by hiding values we know
     (validation uses years <= 2021 for climatology and scores 2022-2023).
  5. Writes data/processed/monthly_filled.csv with fill columns and flags.

Causal = a value at month t only uses data from months before t. This matters:
interpolating across a gap would use FUTURE observations and leak them into
forecasts. Filled values are for model INPUTS only. Never score against them:
evaluate only where optical_valid == 1.
"""
import glob
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]

# ---------- settings ----------
FINAL_TRAIN_END = 2023      # climatology for the final file uses years <= this
VALID_TRAIN_END = 2021      # climatology used while comparing fill methods
VALID_YEARS = (2022, 2023)  # years whose known values are hidden and re-predicted
FILL_METHOD = "clim"        # 'locf' | 'clim' | 'anom'  (set after reading validation)
MAX_AGE = 3                 # beyond this many months since last observation, use climatology
DISTRICT_GAP = 0.05         # month with < 5% valid points = treated as missing
LOW_CONF = 0.5              # month with < 50% valid points = flagged low confidence
MIN_POINTS = 200            # minimum points needed to score a hidden month
VALIDATION_INDEX = "NDMI"

BANDS = ["B3", "B4", "B8", "B11"]
INDICES = ["NDVI", "NDWI", "NDMI"]
OPTICAL = BANDS + INDICES


# ---------- loading and cleaning ----------
def load():
    files = sorted(glob.glob(str(ROOT / "data" / "raw" / "kannur_monthly_*.csv")))
    if not files:
        raise SystemExit("No CSVs found in data/raw/")
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df = df.replace(-9999, np.nan)
    df = df.sort_values(["point_id", "year", "month"]).reset_index(drop=True)
    n_pts = df.point_id.nunique()
    n_t = df[["year", "month"]].drop_duplicates().shape[0]
    assert len(df) == n_pts * n_t, "grid is not complete (points x months)"
    print(f"Loaded {len(files)} files: {n_pts} points x {n_t} months")
    return df, n_pts, n_t


def clean_optical(df):
    bad = ((df[BANDS] > 1).any(axis=1) | (df[BANDS] < 0).any(axis=1) | (df.B4 < 0.005))
    print(f"Rows with extreme reflectance set to missing: {int(bad.sum())}")
    df.loc[bad, OPTICAL] = np.nan

    frac = df.assign(v=df.NDMI.notna()).groupby(["year", "month"]).v.transform("mean")
    gap = frac < DISTRICT_GAP
    print(f"Rows in near-empty months set to missing:     {int((gap & df.NDMI.notna()).sum())}")
    df.loc[gap, OPTICAL] = np.nan

    df["optical_valid"] = df.NDMI.notna().astype(int)
    df["district_valid_frac"] = frac.round(3)
    df["district_gap"] = gap.astype(int)
    df["low_conf_month"] = (frac < LOW_CONF).astype(int)
    df["n_s2"] = df.n_s2.fillna(0)
    return df


def fill_soil(df, n_pts, n_t):
    mat = df.soil_moist.values.reshape(n_pts, n_t).copy()
    allnan = np.isnan(mat).all(axis=1)
    df["soil_moist_filled"] = np.repeat(allnan, n_t).astype(int)
    if allnan.any():
        xy = df.groupby("point_id")[["lon", "lat"]].first().values
        _, idx = cKDTree(xy[~allnan]).query(xy[allnan])
        mat[allnan] = mat[~allnan][idx]
    print(f"Soil moisture: {int(allnan.sum())} masked points filled from nearest valid point; "
          f"remaining NaN = {int(np.isnan(mat).sum())}")
    df["soil_moist"] = mat.ravel()
    return df


def fill_radar(df):
    before = df.VV.isna()
    df[["VV", "VH"]] = df.groupby("point_id")[["VV", "VH"]].ffill(limit=2)
    df["s1_filled"] = (before & df.VV.notna()).astype(int)
    print(f"Radar: {int(df.s1_filled.sum())} rows forward-filled (limit 2 months); "
          f"still missing = {int(df.VV.isna().sum())}")
    return df


# ---------- climatology and causal fills ----------
def climatology(X, months, years, train_end):
    """Per-point mean for each calendar month using years <= train_end only."""
    clim = np.full((X.shape[0], 13), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for m in range(1, 13):
            cols = (months == m) & (years <= train_end)
            clim[:, m] = np.nanmean(X[:, cols], axis=1)
            fallback = np.nanmean(clim[:, m])      # rare: point never valid in this month
            clim[np.isnan(clim[:, m]), m] = fallback
    return clim


def causal_fill(X, months, clim, method, max_age=MAX_AGE):
    N, T = X.shape
    out = X.copy()
    age = np.zeros((N, T), dtype=int)
    last_val = np.full(N, np.nan)
    last_t = np.full(N, -1)
    rows = np.arange(N)
    for t in range(T):
        valid = ~np.isnan(X[:, t])
        a = np.where(last_t >= 0, t - last_t, 99)
        c_t = clim[:, months[t]]
        c_last = clim[rows, months[np.clip(last_t, 0, None)]]
        if method == "locf":
            cand = last_val
        elif method == "anom":
            cand = c_t + (last_val - c_last)
        else:
            cand = c_t
        use = (last_t >= 0) & (a <= max_age) & ~np.isnan(cand)
        pred = np.where(use, cand, c_t)
        out[:, t] = np.where(valid, X[:, t], pred)
        age[:, t] = np.where(valid, 0, np.minimum(a, 99))
        last_val = np.where(valid, X[:, t], last_val)
        last_t = np.where(valid, t, last_t)
    return np.clip(out, -1, 1), age


# ---------- hide-and-test validation ----------
def validate(X, months, years):
    clim = climatology(X, months, years, VALID_TRAIN_END)
    rows = []
    for t in range(X.shape[1]):
        if years[t] not in VALID_YEARS:
            continue
        for L in (1, 2, 3):
            s = t - L          # last real observation before the hidden gap
            if s < 0:
                continue
            ok = (~np.isnan(X[:, t]) & ~np.isnan(X[:, s]))
            if ok.sum() < MIN_POINTS:
                continue
            y = X[ok, t]
            c_t, c_s = clim[ok, months[t]], clim[ok, months[s]]
            preds = {"LOCF": X[ok, s], "CLIM": c_t, "ANOM": c_t + X[ok, s] - c_s}
            for name, p in preds.items():
                e = p - y
                rows.append(dict(year=years[t], month=months[t], gap=L, method=name,
                                 n=int(ok.sum()), sse=float((e ** 2).sum()),
                                 sae=float(np.abs(e).sum())))
    r = pd.DataFrame(rows)
    r["season"] = np.where(r.month.isin([6, 7, 8, 9]), "monsoon (Jun-Sep)", "other months")
    g = r.groupby(["season", "gap", "method"]).agg(n=("n", "sum"), sse=("sse", "sum"),
                                                   sae=("sae", "sum")).reset_index()
    g["RMSE"] = np.sqrt(g.sse / g.n).round(4)
    g["MAE"] = (g.sae / g.n).round(4)
    return g[["season", "gap", "method", "n", "MAE", "RMSE"]]


def plot_validation(g, path):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, (season, sub) in zip(axes, g.groupby("season")):
        p = sub.pivot(index="gap", columns="method", values="RMSE")
        p.plot.bar(ax=ax, rot=0)
        ax.set_title(season)
        ax.set_xlabel("months since last real observation")
    axes[0].set_ylabel(f"RMSE of hidden {VALIDATION_INDEX}")
    fig.suptitle("Gap-fill methods: error on hidden known values")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


# ---------- main ----------
def main():
    tab = ROOT / "results" / "tables"
    fig = ROOT / "results" / "figures"
    out_dir = ROOT / "data" / "processed"
    for d in (tab, fig, out_dir):
        d.mkdir(parents=True, exist_ok=True)

    df, n_pts, n_t = load()
    df = clean_optical(df)
    df = fill_soil(df, n_pts, n_t)
    df = fill_radar(df)

    months = df.month.values[:n_t]
    years = df.year.values[:n_t]
    mat = lambda c: df[c].values.reshape(n_pts, n_t)

    print(f"\nValidating fill methods on {VALIDATION_INDEX} "
          f"(climatology from years <= {VALID_TRAIN_END}, scored on {VALID_YEARS}):")
    g = validate(mat(VALIDATION_INDEX), months, years)
    g.to_csv(tab / "gap_fill_validation.csv", index=False)
    print(g.pivot_table(index=["season", "gap"], columns="method", values="RMSE").to_string())
    plot_validation(g, fig / "gap_fill_validation.png")

    print(f"\nBuilding final filled columns with method '{FILL_METHOD}' "
          f"(climatology from years <= {FINAL_TRAIN_END})")
    for idx in INDICES:
        X = mat(idx)
        clim = climatology(X, months, years, FINAL_TRAIN_END)
        filled, age = causal_fill(X, months, clim, FILL_METHOD)
        df[idx + "_fill"] = filled.ravel()
        if idx == "NDMI":
            df["months_since_obs"] = age.ravel()

    df["date"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1)).dt.strftime("%Y-%m-%d")
    out = out_dir / "monthly_filled.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved {out}  shape={df.shape}")
    print("optical_valid share:", round(df.optical_valid.mean(), 3))
    print("remaining NaN in *_fill columns:", int(df[[i + "_fill" for i in INDICES]].isna().sum().sum()))
    print("REMINDER: score models only where optical_valid == 1.")


if __name__ == "__main__":
    main()