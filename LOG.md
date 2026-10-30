# Project Log

Format: date | who | what was done | settings / file names | notes

| Date                        | Who                                               | What                             | Settings / files                                                                                                                                                                                                              | Notes                                                                                                                                                                            |
| --------------------------- | ------------------------------------------------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|                             |                                                   | Repo created (Stage 0)           |                                                                                                                                                                                                                               |                                                                                                                                                                                  |
| 2026-10-29                  | [name]                                            | GEE access set up                | Cloud project `crop-stress-kannur` (ID: crop-stress-kannur                                                                                                                                                                    |
| ); Earth Engine API enabled | Needed to enable the API before exports would run |
| 2026-10-29                  | [name]                                            | Exported fixed cropland points   | `gee/01_export_points.js`; ESA WorldCover class 40, `stratifiedSample`, scale 100 m, seed 42; Asset `kannur_points`                                                                                                           | First version used `sample()` and gave only 35 points. Fixed with `stratifiedSample`. 1,721 points                                                                               |
| 2026-10-29                  | [name]                                            | Exported monthly data, 2019-2025 | `gee/02_export_monthly.js`; Sentinel-2 L2A (B3, B4, B8, B11) with SCL cloud mask and monthly median; CHIRPS rain; ERA5-Land soil moisture; Sentinel-1 VV/VH; sampled at 20 m; missing = -9999; Drive folder `crop_stress_gee` | Task failed on a band-type mismatch; fixed with `.toFloat()` in `maskS2`. Result: 7 CSVs, 144,564 rows (1,721 points x 84 months)                                                |
| 2026-10-29                  | [name]                                            | Data-quality report              | `src/02_data_quality.py`; `results/tables/data_quality_report.txt`; `results/figures/coverage_heatmap.png`                                                                                                                    | 13.1% of optical rows missing. Empty months: 2022-08, 2024-07, 2025-08. Under 50% valid: 2023-08, 2023-09, 2024-06, 2025-06, 2025-07. No point valid in fewer than 76% of months |
| 2026-10-29                  | [name]                                            | Missing-value diagnostics        | `src/check_missing.py`                                                                                                                                                                                                        | 19 points have no ERA5-Land soil moisture in any month. Radar missing for 4 whole months: 2019-04, 2020-02, 2023-03, 2023-12                                                     |
| 2026-10-30                  | [name]                                            | Gap handling                     | `src/03_gap_handling.py`; `FILL_METHOD = "clim"` [confirm]; final climatology from years <= 2023; output `data/processed/monthly_filled.csv`                                                                                  | Fill methods compared by hiding known NDMI values (climatology from <= 2021, scored on 2022-2023). Climatology beat last-observation and anomaly fills in 5 of 6 cases           |
| 2026-10-30                  | [name]                                            | Verified Stage 3                 | `src/verify_stage3.py`                                                                                                                                                                                                        | All checks passed: 5 extreme-reflectance rows cleared, 6,884 radar rows filled, no NaN in filled columns, real observations unchanged                                            |

## Decisions

- Fills are causal (use only earlier months), because interpolating across a gap would leak future data into forecasts.
- Filled values are used only as model inputs. Score models only where `optical_valid == 1`.
- Monsoon composites often rest on 1-2 images, so they are treated as lower confidence.
- Cropland means the WorldCover cropland class. Tree crops (coconut, rubber, arecanut) are mostly outside it.

## Open items

- Run the July 2022 coverage check (coverage 1.00 in a monsoon month looks suspicious).
- Decide whether to test neighbourhood averaging for pixel noise.
- Optional: test whether 2018 data is usable.
- KVK / Krishibhavan request: [sent on date / not yet sent].
- Stage 4: lag features and the next-month target.
