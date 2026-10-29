"""Stage 2: data-quality report for the Kannur monthly GEE export.

Run from the repo root:   python src/02_data_quality.py
Outputs go to results/figures and results/tables.
"""
import glob
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "results" / "figures"
TAB = ROOT / "results" / "tables"
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)

# ---------- load ----------
files = sorted(glob.glob(str(ROOT / "data" / "raw" / "kannur_monthly_*.csv")))
df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
df = df.replace(-9999, np.nan)
df["valid"] = df["NDMI"].notna()
df["date"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1))
print(f"Loaded {len(files)} files, {df.shape[0]} rows, {df.point_id.nunique()} points")

# ---------- 1. coverage table + heatmap ----------
cov = df.pivot_table(index="year", columns="month", values="valid", aggfunc="mean")
cov.round(2).to_csv(TAB / "coverage_year_month.csv")

fig, ax = plt.subplots(figsize=(9, 4))
im = ax.imshow(cov.values, vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
ax.set_xticks(range(12), range(1, 13))
ax.set_yticks(range(len(cov)), cov.index)
ax.set_xlabel("Month")
ax.set_ylabel("Year")
ax.set_title("Fraction of cropland points with a valid optical composite")
for i in range(cov.shape[0]):
    for j in range(cov.shape[1]):
        ax.text(j, i, f"{cov.values[i, j]:.2f}", ha="center", va="center", fontsize=7)
fig.colorbar(im, ax=ax, label="valid fraction")
fig.tight_layout()
fig.savefig(FIG / "coverage_heatmap.png", dpi=200)
plt.close(fig)

flat = cov.stack()
low = flat[flat < 0.5]
print("\nMonths with <50% valid coverage:")
print(low.round(2).to_string())
print("\nMonths with <5% coverage (treat as missing):")
print(flat[flat < 0.05].round(2).to_string())

# ---------- 2. monthly series (mask very low-coverage months) ----------
monthly = df.groupby("date").agg(
    NDVI=("NDVI", "mean"), NDMI=("NDMI", "mean"),
    rain_mm=("rain_mm", "mean"), valid=("valid", "mean"),
)
monthly.loc[monthly.valid < 0.2, ["NDVI", "NDMI"]] = np.nan  # unreliable months
monthly.round(3).to_csv(TAB / "monthly_means.csv")

fig, ax = plt.subplots(figsize=(12, 4))
ax.bar(monthly.index, monthly.rain_mm, width=20, color="#c6dbef", label="Rainfall (mm/month)")
ax.set_ylabel("Rainfall (mm)")
ax2 = ax.twinx()
ax2.plot(monthly.index, monthly.NDVI, "g.-", label="NDVI")
ax2.plot(monthly.index, monthly.NDMI, "r.-", label="NDMI")
ax2.axhline(0, color="grey", lw=0.5)
ax2.set_ylabel("Mean index")
ax.set_title("Monthly mean NDVI, NDMI and rainfall (months with <20% valid points left blank)")
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "monthly_series.png", dpi=200)
plt.close(fig)

# ---------- 3. cloud-contamination check (monsoon months) ----------
mon = df[df.month.isin([6, 7, 8, 9]) & df.valid].copy()
mon["n_s2_bin"] = pd.cut(mon.n_s2, [-1, 0, 1, 2, 4, 100],
                         labels=["0", "1", "2", "3-4", "5+"])
contam = mon.groupby("n_s2_bin", observed=True).agg(
    rows=("NDMI", "size"), mean_NDMI=("NDMI", "mean"), mean_NDVI=("NDVI", "mean")).round(3)
contam.to_csv(TAB / "ndmi_by_n_s2_monsoon.csv")
print("\nMonsoon NDMI by number of clear observations (n_s2):")
print(contam.to_string())

# ---------- 4. outliers and missing values ----------
print("\nFraction missing per column:")
cols = ["B3", "B4", "B8", "B11", "NDVI", "NDWI", "NDMI",
        "rain_mm", "soil_moist", "VV", "VH", "n_s2"]
miss = df[cols].isna().mean().round(3)
miss.to_csv(TAB / "missing_by_column.csv")
print(miss.to_string())

print("\nPossible outliers (kept, flagged only):")
print("  NDVI > 0.95  :", int((df.NDVI > 0.95).sum()))
print("  NDWI < -0.9  :", int((df.NDWI < -0.9).sum()))
print("  NDMI > 0.7   :", int((df.NDMI > 0.7).sum()))

# ---------- 5. per-point coverage ----------
pt = df.groupby("point_id").valid.mean()
pt.describe().round(3).to_csv(TAB / "point_coverage_summary.csv")
print("\nPer-point valid fraction (over all months):")
print(pt.describe().round(3).to_string())
print("Points valid in <70% of months:", int((pt < 0.7).sum()))

# ---------- 6. year-to-year consistency ----------
dry = df[df.month.isin([3, 4]) & df.valid].groupby("year").NDMI.mean().round(3)
wet = df[df.month.isin([8, 9]) & df.valid].groupby("year").NDMI.mean().round(3)
print("\nMean NDMI, Mar-Apr by year:\n", dry.to_string())
print("\nMean NDMI, Aug-Sep by year:\n", wet.to_string())

print("\nSaved figures to", FIG, "and tables to", TAB)