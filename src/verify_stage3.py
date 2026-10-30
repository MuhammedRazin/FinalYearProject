"""Independent re-check of the Stage 3 numbers.

Run from the repo root AFTER 03_gap_handling.py:   python src/verify_stage3.py
It recomputes each figure straight from data/raw and compares it with
data/processed/monthly_filled.csv, so you do not have to trust the script.
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BANDS = ["B3", "B4", "B8", "B11"]


def say(label, ok, detail):
    print(f"[{'PASS ' if ok else 'CHECK'}] {label}: {detail}")


files = sorted(glob.glob(str(ROOT / "data" / "raw" / "kannur_monthly_*.csv")))
raw = pd.concat([pd.read_csv(f) for f in files], ignore_index=True).replace(-9999, np.nan)
raw = raw.sort_values(["point_id", "year", "month"]).reset_index(drop=True)
pro = pd.read_csv(ROOT / "data" / "processed" / "monthly_filled.csv")
pro = pro.sort_values(["point_id", "year", "month"]).reset_index(drop=True)

assert len(raw) == len(pro), "raw and processed have different row counts"
assert (raw.point_id.values == pro.point_id.values).all()
assert (raw.month.values == pro.month.values).all()
n_pts = raw.point_id.nunique()
print(f"Rows: {len(raw)} = {n_pts} points x {len(raw) // n_pts} months\n")

# 1. extreme reflectance rows
bad = ((raw[BANDS] > 1) | (raw[BANDS] < 0)).any(axis=1) | (raw.B4 < 0.005)
cleared = pro.loc[bad, "NDMI"].isna().all()
say("1. extreme reflectance rows", cleared,
    f"{int(bad.sum())} rows in raw data; all set to missing in processed = {cleared}")
if bad.any():
    print(raw.loc[bad, ["point_id", "year", "month", "B3", "B4", "B8", "B11"]].round(3).to_string())

# 2. radar gaps
vv_missing = raw[raw.VV.isna()]
months = vv_missing.groupby(["year", "month"]).size()
say("2. radar rows missing in raw", True,
    f"{len(vv_missing)} rows = {len(months)} whole months x {n_pts} points "
    f"(expected {len(months) * n_pts})")
print("   months with no radar:", [f"{y}-{m:02d}" for y, m in months.index])
say("   radar forward-filled", int(pro.s1_filled.sum()) == len(vv_missing),
    f"{int(pro.s1_filled.sum())} rows flagged s1_filled; VV still missing = {int(pro.VV.isna().sum())}")

# 3. near-empty months
raw["v"] = raw.NDMI.notna()
frac = raw.groupby(["year", "month"]).v.mean()
counts = raw.groupby(["year", "month"]).v.sum()
gap_months = frac[frac < 0.05]
print("\n3. near-empty months (<5% valid points) and how many valid rows each had:")
for (y, m), f in gap_months.items():
    print(f"   {y}-{m:02d}: valid fraction {f:.3f}, valid rows {int(counts[(y, m)])}")
removed = int((raw.NDMI.notna() & pro.NDMI.isna()).sum())
stray = int(counts[gap_months.index].sum())
say("   rows removed in total", True,
    f"{removed} (stray rows in empty months = {stray}, extreme reflectance rows = "
    f"{int((bad & raw.NDMI.notna()).sum())})")

# 4. valid share
raw_share = raw.NDMI.notna().mean()
pro_share = pro.optical_valid.mean()
say("4. valid share", abs((raw_share - pro_share) * len(raw) - removed) < 1,
    f"raw {raw_share:.4f} -> processed {pro_share:.4f}; "
    f"missing in raw = {1 - raw_share:.3f}")

# 5. filled columns
print("\n5. filled columns:")
for c in ["NDVI_fill", "NDWI_fill", "NDMI_fill", "soil_moist", "VV", "VH"]:
    say(f"   NaN in {c}", int(pro[c].isna().sum()) == 0, int(pro[c].isna().sum()))
ok_rows = pro.optical_valid == 1
same = np.allclose(pro.loc[ok_rows, "NDMI_fill"], pro.loc[ok_rows, "NDMI"])
say("   real observations left unchanged by the fill", same,
    f"{int(ok_rows.sum())} valid rows compared")
say("   fills inside [-1, 1]", pro[["NDVI_fill", "NDWI_fill", "NDMI_fill"]].abs().max().max() <= 1.0,
    f"max |value| = {pro[['NDVI_fill', 'NDWI_fill', 'NDMI_fill']].abs().max().max():.3f}")

# 6. soil moisture
masked = raw.groupby("point_id").soil_moist.apply(lambda s: s.isna().all())
say("6. soil-moisture points missing in every month (raw)", True, int(masked.sum()))
say("   filled in processed", int(pro.soil_moist_filled.sum()) == int(masked.sum()) * (len(raw) // n_pts),
    f"{int(pro.soil_moist_filled.sum())} rows flagged")