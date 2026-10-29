import pandas as pd, numpy as np, glob
df = pd.concat([pd.read_csv(f) for f in sorted(glob.glob("data/raw/kannur_monthly_*.csv"))])
df = df.replace(-9999, np.nan)

cols = ["B3","B4","B8","B11","NDVI","NDWI","NDMI","rain_mm","soil_moist","VV","VH","n_s2"]
print("fraction missing:")
print(df[cols].isna().mean().round(3))
print("\nmin / median / max:")
print(df[cols].describe().loc[["min","50%","max"]].round(3).T)
print("\nNDVI > 0.95:", (df.NDVI > 0.95).sum(), "  NDWI < -0.9:", (df.NDWI < -0.9).sum())
print("\nsoil moisture by year:")
print(df.groupby("year")["soil_moist"].agg(["min","mean","max"]).round(3))