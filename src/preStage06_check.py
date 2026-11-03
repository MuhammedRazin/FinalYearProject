"""Pre-Stage-6 consistency checks.

Run from the repo root:   python src/pre_stage6_checks.py

Checks that the pipeline files belong together (nothing stale), that the fill method
in the data is the one you think it is, that the splits look sane, and prints the
numbers you need to interpret Stage 6 (thin months, class mix, the July 2022 question).
"""
import glob
import json
import re
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"


def say(label, ok, detail=""):
    print(f"[{'PASS ' if ok else 'CHECK'}] {label}" + (f": {detail}" if detail else ""))


pro = pd.read_csv(P / "monthly_filled.csv")
feat = pd.read_csv(P / "features.csv")
meta = json.loads((P / "feature_list.json").read_text())

# 1. which fill method is actually in the data? ------------------------------------------
text = (ROOT / "src" / "03_gap_handling.py").read_text()
m = re.search(r'^FILL_METHOD\s*=\s*"(\w+)"', text, re.M)
method = m.group(1) if m else "unknown"
f = pro[pro.optical_valid == 0].copy()
f["n"] = f.groupby(["point_id", "month"]).NDMI_fill.transform("size")
g = f[f.n >= 2].groupby(["point_id", "month"]).NDMI_fill.agg(["max", "min"])
frac_diff = float(((g["max"] - g["min"]) > 1e-6).mean())
print("1. FILL METHOD")
say("FILL_METHOD in src/03_gap_handling.py", method == "clim", f'"{method}"')
say("data really contains climatology fills", frac_diff < 0.01,
    f"{100 * frac_diff:.1f}% of (point, month) groups have fills that differ between years "
    "(climatology fills are identical across years, so this should be ~0%)")

# 2. are the files in the right order (nothing stale)? ------------------------------------
print("\n2. FILE ORDER (each file should be newer than the one before it)")
raw_files = glob.glob(str(ROOT / "data" / "raw" / "kannur_monthly_*.csv"))
chain = [("raw CSVs (newest)", max(Path(x).stat().st_mtime for x in raw_files)),
         ("src/03_gap_handling.py", (ROOT / "src" / "03_gap_handling.py").stat().st_mtime),
         ("monthly_filled.csv", (P / "monthly_filled.csv").stat().st_mtime),
         ("features.csv", (P / "features.csv").stat().st_mtime),
         ("src/05_train.py", (ROOT / "src" / "05_train.py").stat().st_mtime),
         ("models/rf_reg.pkl", (ROOT / "models" / "rf_reg.pkl").stat().st_mtime)]
for name, t in chain:
    print(f"   {datetime.fromtimestamp(t):%Y-%m-%d %H:%M}  {name}")
# the script files may be edited after data was built, so compare only data -> data -> models
order_ok = (chain[0][1] <= chain[2][1] <= chain[3][1] <= chain[5][1])
say("raw -> monthly_filled -> features -> models", order_ok,
    "rerun the earlier stage if this fails" if not order_ok else "")
say("models newer than 05_train.py (so the patched script produced them)",
    chain[5][1] >= chain[4][1], "retrain with the current script" if chain[5][1] < chain[4][1] else "")

# 3. features and models agree ------------------------------------------------------------
print("\n3. FEATURE LIST")
feats = meta["features"]
say("all listed features exist in features.csv", set(feats) <= set(feat.columns))
rf = joblib.load(ROOT / "models" / "rf_reg.pkl")
say("saved model expects the same number of features", rf.n_features_in_ == len(feats),
    f"model {rf.n_features_in_}, list {len(feats)}")
mf = json.loads((ROOT / "models" / "feature_list.json").read_text())["features"]
say("models/feature_list.json equals data/processed/feature_list.json", mf == feats)

# 4. splits --------------------------------------------------------------------------------
print("\n4. SPLITS")
s = (feat.groupby(["split_time", "spatial_holdout"])
         .agg(rows=("point_id", "size"), points=("point_id", "nunique"),
              scorable=("target_valid", "sum")).reset_index())
print(s.to_string(index=False))
hold = feat[feat.spatial_holdout == 1]
say("hold-out blocks never overlap training blocks",
    not set(hold.block_id) & set(feat[feat.spatial_holdout == 0].block_id),
    f"{hold.point_id.nunique()} hold-out points in {hold.block_id.nunique()} blocks "
    f"({100 * hold.point_id.nunique() / feat.point_id.nunique():.0f}% of points)")

# 5. scorable rows by month (thin months matter when you read Stage 6) ---------------------
print("\n5. SCORABLE ROWS (target_valid=1, seen points) PER TARGET MONTH")
sc = feat[(feat.target_valid == 1) & (feat.spatial_holdout == 0) & feat.split_time.isin(["val", "test"])]
tbl = sc.pivot_table(index="target_month", columns="target_year", values="point_id", aggfunc="size").fillna(0).astype(int)
print(tbl.to_string())
n_seen = feat[feat.spatial_holdout == 0].point_id.nunique()
thin = [(int(y), int(mo)) for y in tbl.columns for mo, n in tbl[y].items() if n < 0.4 * n_seen]
print(f"   months with scorable rows for under 40% of the {n_seen} seen points "
      "(read results for these with care):", thin)

# 6. class mix ------------------------------------------------------------------------------
print("\n6. PROXY CLASS MIX (scorable rows; 0 Low, 1 Moderate, 2 High)")
cm = (feat[feat.target_valid == 1].groupby("split_time").target_class_proxy
      .value_counts(normalize=True).unstack().round(3))
print(cm.to_string())

# 7. the July 2022 question --------------------------------------------------------------------
print("\n7. JUNE-SEPTEMBER 2022 (July showed 100% valid points in a monsoon month)")
x = pro[(pro.year == 2022) & pro.month.isin([6, 7, 8, 9])]
print(x.groupby("month").agg(valid_frac=("optical_valid", "mean"), mean_n_s2=("n_s2", "mean"),
                              rain_mm=("rain_mm", "mean"), NDVI=("NDVI", "mean"),
                              NDMI=("NDMI", "mean"), B4=("B4", "mean")).round(3).to_string())
print("   Compare July with June and September. If n_s2 is about 1 and NDVI/NDMI are far higher "
      "than neighbours, treat July 2022 as low confidence.")