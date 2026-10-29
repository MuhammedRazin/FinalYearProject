import pandas as pd, numpy as np, glob

df = pd.concat([pd.read_csv(f) for f in sorted(glob.glob("data/raw/kannur_monthly_*.csv"))])
df = df.replace(-9999, np.nan)

# 1. soil moisture: same points every month, or scattered?
sm = df.groupby("point_id").soil_moist.apply(lambda s: s.isna().mean())
print("points with any missing soil_moist:", int((sm > 0).sum()))
print("points missing in EVERY month:     ", int((sm == 1).sum()))

# 2. radar: whole months, or scattered points?
s1 = df.groupby(["year", "month"]).VV.apply(lambda s: s.isna().mean())
print("\nyear-months with missing VV (fraction of points):")
print(s1[s1 > 0].round(2).to_string())

# 3. extreme reflectances
print("\nrows with B3 or B4 > 1:", int((df[["B3", "B4"]] > 1).any(axis=1).sum()))
print("rows with B4 < 0.005:  ", int((df.B4 < 0.005).sum()))