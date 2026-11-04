"""Stage 8: equal-history comparison (does the model need less history than climatology?).

Run from the repo root (after 07_rolling_origin.py):   python src/08_equal_history.py
Takes roughly 15-30 minutes (24 Random Forest fits).

Stage 7 showed the Random Forest error is roughly constant across test years while the
climatology error falls as it gains history. This script tests that explanation directly.

For each test year Y and history length H (years):
  * the Random Forest is trained ONLY on rows whose target month is in the H years before Y
    (hold-out points excluded), and
  * the climatology is built ONLY from the same H years.
So both methods see exactly the same amount of history. H = "all" uses every year before Y.

Outputs
  A. per (test year, H): RMSE of climatology, RF and blend, and the gains
  B. test years 2024 and 2025 pooled (same rows for every H): the cleanest comparison
  C. cross-comparison: RF trained on a short history vs climatology built from ALL history

Seen points only, one seed (42), scorable rows only. The blend (50/50) is exploratory.
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

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
SEED, N_BOOT = 42, 1000
FOLD_YEARS = (2021, 2022, 2023, 2024, 2025)
HIST = (1, 2, 3, 4, 5, "all")
COMMON = (2024, 2025)          # test years for which every history length is available
FIRST_YEAR = 2019


def rmse(e):
    return float(np.sqrt(np.mean(np.square(e))))


def load():
    P = ROOT / "data" / "processed"
    feat = pd.read_csv(P / "features.csv")
    feats = json.loads((P / "feature_list.json").read_text())["features"]
    pro = pd.read_csv(P / "monthly_filled.csv", usecols=["point_id", "year", "month", "NDMI"])
    return feat[feat.lags_complete == 1].copy(), feats, pro


def run(d, feats, pro, Y, H):
    lo = FIRST_YEAR if H == "all" else Y - H
    if lo < FIRST_YEAR:
        return None
    tr = d[(d.target_year >= lo) & (d.target_year < Y) & (d.spatial_holdout == 0)].dropna(subset=["target_NDMI"])
    hist = pro[(pro.year >= lo) & (pro.year < Y)]
    c = (hist.groupby(["point_id", "month"]).NDMI.mean().rename("clim").reset_index()
             .rename(columns={"month": "target_month"}))
    month_mean = hist.groupby("month").NDMI.mean()
    te = d[(d.target_year == Y) & (d.target_valid == 1) & d.target_NDMI.notna()
           & (d.spatial_holdout == 0)].merge(c, on=["point_id", "target_month"], how="left")
    te["clim"] = te.clim.fillna(te.target_month.map(month_mean))
    rf = RandomForestRegressor(n_estimators=200, max_features=0.4, min_samples_leaf=5,
                               n_jobs=-1, random_state=SEED)
    rf.fit(tr[feats].values.astype(float), tr.target_NDMI.values)
    out = pd.DataFrame({"fold": Y, "H": str(H), "point_id": te.point_id.values,
                        "block_id": te.block_id.values,
                        "ym": (te.target_year * 100 + te.target_month).values,
                        "y": te.target_NDMI.values, "clim": te.clim.values,
                        "RF": rf.predict(te[feats].values.astype(float))})
    out["blend"] = 0.5 * out.RF + 0.5 * out.clim
    print(f"  test {Y}, history {H}: trained on {len(tr):,} rows, scored {len(te):,}")
    return out


def cluster_gain(df, pred, base, key, rng):
    t = pd.DataFrame({"k": df[key].values, "m": (df.y - df[pred]).values ** 2,
                      "b": (df.y - df[base]).values ** 2, "n": 1.0}).groupby("k").sum()
    idx = rng.integers(0, len(t), size=(N_BOOT, len(t)))
    sm, sb, n = t.m.values, t.b.values, t.n.values
    v = 100 * (1 - np.sqrt(sm[idx].sum(1) / n[idx].sum(1)) / np.sqrt(sb[idx].sum(1) / n[idx].sum(1)))
    lo, mid, hi = np.percentile(v, [2.5, 50, 97.5])
    return f"{mid:+.1f} [{lo:+.1f}, {hi:+.1f}]"


def main():
    tab = ROOT / "results" / "tables"
    fig = ROOT / "results" / "figures"
    tab.mkdir(parents=True, exist_ok=True)
    fig.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    d, feats, pro = load()

    print("FITTING")
    parts = [run(d, feats, pro, Y, H) for Y in FOLD_YEARS for H in HIST]
    res = pd.concat([p for p in parts if p is not None], ignore_index=True)
    order = [str(h) for h in HIST]

    # ---------- A. per test year and history length ----------
    rows = []
    for (Y, H), g in res.groupby(["fold", "H"]):
        rows.append(dict(test_year=Y, history=H, n=len(g), RMSE_clim=rmse(g.y - g.clim),
                         RMSE_RF=rmse(g.y - g.RF), RMSE_blend=rmse(g.y - g.blend)))
    A = pd.DataFrame(rows)
    A["gain_RF_%"] = 100 * (1 - A.RMSE_RF / A.RMSE_clim)
    A["gain_blend_%"] = 100 * (1 - A.RMSE_blend / A.RMSE_clim)
    A.round(4).to_csv(tab / "stage8_equal_history.csv", index=False)
    pd.set_option("display.width", 200)
    for col, title in (("RMSE_clim", "CLIMATOLOGY RMSE"), ("RMSE_RF", "RANDOM FOREST RMSE"),
                       ("gain_RF_%", "RF GAIN VS CLIMATOLOGY AT EQUAL HISTORY (%)"),
                       ("gain_blend_%", "BLEND GAIN VS CLIMATOLOGY AT EQUAL HISTORY (%)")):
        pv = A.pivot(index="test_year", columns="history", values=col)[[h for h in order if h in set(A.history)]]
        print(f"\nA. {title}   (rows = test year, columns = years of history)")
        print(pv.round(4 if "RMSE" in col else 1).to_string())

    # ---------- B. common test years, every history length ----------
    com = res[res.fold.isin(COMMON)]
    rowsB = []
    for H in order:
        g = com[com.H == H]
        rowsB.append(dict(history=H, n=len(g), RMSE_clim=rmse(g.y - g.clim), RMSE_RF=rmse(g.y - g.RF),
                          RMSE_blend=rmse(g.y - g.blend),
                          gain_RF_ym=cluster_gain(g, "RF", "clim", "ym", rng),
                          gain_RF_block=cluster_gain(g, "RF", "clim", "block_id", rng),
                          gain_blend_ym=cluster_gain(g, "blend", "clim", "ym", rng)))
    B = pd.DataFrame(rowsB)
    B.to_csv(tab / "stage8_common_years.csv", index=False)
    print(f"\nB. TEST YEARS {COMMON} POOLED (identical rows for every history length)")
    print(B.round(4).to_string(index=False))

    # ---------- C. short-history RF vs long-history climatology ----------
    allc = res[res.H == "all"][["fold", "point_id", "ym", "clim"]].rename(columns={"clim": "clim_all"})
    rowsC = []
    for H in ("1", "2", "3"):
        g = res[(res.H == H) & res.fold.isin(COMMON)].merge(allc, on=["fold", "point_id", "ym"])
        r = {"RF_history": H, "n": len(g), "RMSE_RF": rmse(g.y - g.RF),
             "RMSE_clim_all_history": rmse(g.y - g.clim_all)}
        r["gain_vs_clim_all_%"] = 100 * (1 - r["RMSE_RF"] / r["RMSE_clim_all_history"])
        for Y in COMMON:
            gy = g[g.fold == Y]
            r[f"gain_{Y}_%"] = 100 * (1 - rmse(gy.y - gy.RF) / rmse(gy.y - gy.clim_all))
        r["ci_ym"] = cluster_gain(g.assign(c=g.clim_all), "RF", "c", "ym", rng)
        rowsC.append(r)
    C = pd.DataFrame(rowsC)
    C.round(4).to_csv(tab / "stage8_cross.csv", index=False)
    print(f"\nC. RF TRAINED ON SHORT HISTORY vs CLIMATOLOGY FROM ALL HISTORY (test years {COMMON})")
    print(C.round(3).to_string(index=False))

    # ---------- integrity check against Stage 7 ----------
    s7 = tab / "stage7_rolling_origin.csv"
    if s7.exists():
        s7d = pd.read_csv(s7).set_index("fold").RMSE_RandomForest
        mine = A[A.history == "all"].set_index("test_year").RMSE_RF
        diff = (mine - s7d.reindex(mine.index)).abs().max()
        print(f"\nCHECK: RF with all history vs Stage 7 RF, largest RMSE difference = {diff:.5f} "
              "(should be about 0; small differences come from the row filter)")

    # ---------- figure ----------
    f, ax = plt.subplots(figsize=(7, 4.5))
    xs = np.arange(len(order))
    ax.plot(xs, B.RMSE_clim, "o-", label="Climatology")
    ax.plot(xs, B.RMSE_RF, "s-", label="Random Forest")
    ax.plot(xs, B.RMSE_blend, "^--", label="Blend (exploratory)")
    ax.set_xticks(xs, order)
    ax.set_xlabel("years of history available to both methods")
    ax.set_ylabel(f"RMSE, test years {COMMON[0]}-{COMMON[-1]}")
    ax.set_title("Does the model need less history than climatology?")
    ax.legend()
    f.tight_layout()
    f.savefig(fig / "stage8_history_curve.png", dpi=200)
    plt.close(f)

    print("\n[DONE] tables: results/tables/stage8_*.csv   figure: results/figures/stage8_history_curve.png")
    print("HOW TO READ: if the RF gain in B stays clearly positive at short history and shrinks or "
          "vanishes at long history, the data-efficiency explanation holds. If RF is not better than "
          "climatology even at 1-2 years, it does not. Section C asks whether 1-3 years of RF data "
          "can match climatology built from every year.")


if __name__ == "__main__":
    main()
