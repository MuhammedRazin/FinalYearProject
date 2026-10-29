import pandas as pd, numpy as np, glob

files = sorted(glob.glob("data/raw/kannur_monthly_*.csv"))
print("files found:", [f[-8:-4] for f in files])
df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
df = df.replace(-9999, np.nan)

print("\nshape:", df.shape)
print("unique points:", df["point_id"].nunique())
print("\nrows per year (expect 20652 each):")
print(df.groupby("year").size())
print("\nindex ranges (should be between -1 and 1):")
print(df[["NDVI", "NDWI", "NDMI"]].describe().loc[["min", "max"]])

monthly = df.groupby(["year", "month"]).agg(
    valid_frac=("NDMI", lambda s: s.notna().mean()),
    NDMI=("NDMI", "mean"),
    NDVI=("NDVI", "mean"),
    rain_mm=("rain_mm", "mean"),
).round(2)
print("\nmonthly summary:")
print(monthly.to_string())