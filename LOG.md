# Project Log

Format: date | who | what was done | settings / file names | notes

| Date       | Who    | What                                                            | Settings / files                                                                                                                                                                                                                                                                                                                                                                              | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ---------- | ------ | --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [date]     | [name] | Repo created (Stage 0)                                          | Folders: gee, data, notebooks, src, dashboard, report, results                                                                                                                                                                                                                                                                                                                                |                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| 2026-10-29 | [name] | GEE access set up                                               | Cloud project `crop-stress-kannur`; Earth Engine API enabled                                                                                                                                                                                                                                                                                                                                  | Needed to enable the API before exports would run                                                                                                                                                                                                                                                                                                                                                                                               |
| 2026-10-29 | [name] | Exported fixed cropland points                                  | `gee/01_export_points.js`; ESA WorldCover class 40, `stratifiedSample`, scale 100 m, seed 42; Asset `kannur_points`                                                                                                                                                                                                                                                                           | First version used `sample()` and gave only 35 points. Fixed with `stratifiedSample`. 1,721 points                                                                                                                                                                                                                                                                                                                                              |
| 2026-10-29 | [name] | Exported monthly data, 2019-2025                                | `gee/02_export_monthly.js`; Sentinel-2 L2A (B3, B4, B8, B11) with SCL cloud mask and monthly median; CHIRPS rain; ERA5-Land soil moisture; Sentinel-1 VV/VH; sampled at 20 m; missing = -9999; Drive folder `crop_stress_gee`                                                                                                                                                                 | Task failed on a band-type mismatch; fixed with `.toFloat()` in `maskS2`. Result: 7 CSVs, 144,564 rows (1,721 points x 84 months)                                                                                                                                                                                                                                                                                                               |
| 2026-10-29 | [name] | Data-quality report                                             | `src/02_data_quality.py`; `results/tables/data_quality_report.txt`; `results/figures/coverage_heatmap.png`                                                                                                                                                                                                                                                                                    | 13.1% of optical rows missing. Empty months: 2022-08, 2024-07, 2025-08. Under 50% valid: 2023-08, 2023-09, 2024-06, 2025-06, 2025-07. No point valid in fewer than 76% of months                                                                                                                                                                                                                                                                |
| 2026-10-29 | [name] | Missing-value diagnostics                                       | `src/check_missing.py`                                                                                                                                                                                                                                                                                                                                                                        | 19 points have no ERA5-Land soil moisture in any month. Radar missing for 4 whole months: 2019-04, 2020-02, 2023-03, 2023-12                                                                                                                                                                                                                                                                                                                    |
| 2026-10-30 | [name] | Gap handling                                                    | `src/03_gap_handling.py`; `FILL_METHOD = "clim"`; final climatology from years <= 2023; output `data/processed/monthly_filled.csv`                                                                                                                                                                                                                                                            | Fill methods compared by hiding known NDMI values (climatology from <= 2021, scored on 2022-2023). Climatology beat last-observation and anomaly fills in 5 of 6 cases                                                                                                                                                                                                                                                                          |
| 2026-10-30 | [name] | Verified Stage 3                                                | `src/verify_stage3.py`                                                                                                                                                                                                                                                                                                                                                                        | All checks passed: 5 extreme-reflectance rows cleared, 6,884 radar rows filled, no NaN in filled columns, real observations unchanged                                                                                                                                                                                                                                                                                                           |
| 2026-10-31 | [name] | Feature table (Stage 4)                                         | `src/04_features.py`; output `data/processed/features.csv` (~93 MB), `data/processed/feature_list.json`; 38 features (current month + lags 1-3 for NDMI/NDVI/NDWI/rain/soil/VV/VH + rain sums + NDMI diff + month sin/cos); target = real NDMI at t+1; splits: train <= 2023, val = 2024, test = 2025; spatial hold-out = 20% of 0.1 degree blocks (224 points, about 13% of points, seed 42) | All 7 checks passed (5 leakage/alignment checks + 2 split checks). Scorable rows (target_valid = 1, all points): train 91,366, val 16,908, test 15,606. Summary in `results/tables/feature_table_summary.csv`                                                                                                                                                                                                                                   |
| 2026-10-31 | [name] | Model training, first run (Stage 5)                             | `src/05_train.py` (original version); Ridge, Random Forest (n=300), XGBoost (n=500, lr=0.05); scored on scorable val rows (target_valid=1, spatial_holdout=0, 14,792 rows)                                                                                                                                                                                                                    | **Superseded.** Training filter did not exclude the hold-out points (86,203 train rows, all 1,721 points). See the 2026-11-03 correction. Results were almost identical to the rerun                                                                                                                                                                                                                                                            |
| 2026-11-03 | [name] | Correction: hold-out excluded from training, Stage 5 rerun      | `src/05_train.py` (patched): train = split_time "train" AND spatial_holdout 0; class baselines added; confusion matrix plots the classifier with the higher weighted F1; old tables moved to `results/tables/old_run/`                                                                                                                                                                        | 74,948 train rows from 1,497 points. Validation scores essentially unchanged. RF RMSE 0.0860 (-7.8% vs climatology), R2 0.797. RF accuracy 0.784 vs seasonal-naive 0.762 and climatology 0.754. Details below                                                                                                                                                                                                                                   |
| 2026-11-03 | [name] | Pre-Stage-6 consistency checks                                  | `src/pre_stage6_checks.py`; `results/tables/pre_stage6_checks.txt`                                                                                                                                                                                                                                                                                                                            | All checks passed: fill method is climatology in both the setting and the data; raw -> filled -> features -> models are in order; model and feature list agree (38). Hold-out = 224 points but only 5 blocks. Thin test months: 2025-07 (344 scorable rows), 2025-08 (0), 2024-07 (0). Class mix stable across splits (Low 0.40-0.43)                                                                                                           |
| 2026-11-03 | [name] | Stage 6 first full evaluation (validation AND 2025 test scored) | `src/06_evaluate.py` with `EVALUATE_TEST = True`; `results/tables/stage6_*.csv`; report in `results/tables/stage6_report.txt`                                                                                                                                                                                                                                                                 | The script default was True, so the test sets were scored in the first run. RF beat climatology by 7.8% RMSE in 2024 but not in 2025 (-1.4% seen points, +2.1% unseen). 2025 accuracy is below the seasonal baselines. Details in the Stage 6 section. Do not tune on the test set from here                                                                                                                                                    |
| 2026-11-03 | [name] | Stage 7: rolling-origin evaluation and two diagnostics          | `src/07_rolling_origin.py`; folds 2021-2025, train on earlier years, climatology recomputed per fold; `results/tables/stage7_*.csv`, `results/figures/stage7_*.png`; report in `results/tables/stage7_report.txt`                                                                                                                                                                             | RF gain vs climatology by test year: +24.5, +21.2, +12.1, +7.8, -4.8 (%). RF RMSE stays about 0.086-0.098 while climatology improves from 0.124 to 0.093 as history grows. Oracle with next-month rain adds little. Rain-anomaly hypothesis not supported. Blend with climatology is better than climatology in 2023-2025 (exploratory)                                                                                                         |
| 2026-11-03 | [name] | Stage 8: equal-history comparison                               | `src/08_equal_history.py`; random forest and climatology given the same 1, 2, 3, 4, 5 or all years of history for each test year 2021-2025; `results/tables/stage8_*.csv`, `results/figures/stage8_history_curve.png`; report in `results/tables/stage8_report.txt`                                                                                                                           | Integrity check against Stage 7 passed (RMSE difference 0.00004). Pooled 2024-2025: RF gain vs climatology +11.5% (1 yr), +14.0% (2 yrs), +2.6% (3), +0.4% (4), -0.9% (5), +1.9% (all), all month-level intervals include zero. RF with 1-2 years is about equal to climatology with all years (+1.7%, +3.5%, intervals include zero). 2025 flips from +13.6% to -10.0% when 2022 enters the training window. Blend is positive in all 24 cells |

## Decisions

- Fills are causal (use only earlier months), because interpolating across a gap would leak future data into forecasts.
- Filled values are used only as model inputs. Score models only where `optical_valid == 1` (`target_valid == 1` for targets).
- Monsoon composites often rest on 1-2 images, so they are treated as lower confidence.
- Cropland means the WorldCover cropland class. Tree crops (coconut, rubber, arecanut) are mostly outside it.
- The spatial hold-out points are excluded from training and validation and are scored only in Stage 6.
- The 2025 test set is scored once, after the models are final. Use `EVALUATE_TEST = False` in `06_evaluate.py` until then.
- Primary regression and classification model: Random Forest. XGBoost is statistically a tie (see Stage 5 results), so the choice is for interpretability.
- Wording for the report: the models beat climatology on the 2024 validation year (about 8% lower RMSE) but not on the 2025 test year, so an improvement over climatology is not established across years. Do not describe them as accurately detecting crop stress.
- The 2025 test set has been scored and is no longer untouched. Any model change must be judged by rolling-origin evaluation over several years, not by 2025 alone.
- Do not quote the pooled +14% gain over climatology from Stage 7. It is dominated by early folds where the climatology baseline had only 2-3 years of history. Report the gain per fold.
- The 50/50 RF + climatology blend is exploratory: it was proposed after the Stage 6 results were seen, so its 2024 and 2025 results are not a clean test.
- Do not choose the training window, history length or model settings by their effect on the 2025 results. 2025 has been seen.

## Known limitations

- Stress classes are thresholds on NDMI itself, so classification results show forecasting skill on a proxy label, not validated crop stress.
- No field data. ERA5-Land (about 9 km) and SMAP are modelled or coarse products, so validation is regional and shows agreement, not field accuracy.
- The climatology fill for training rows includes later training years, so it is slightly leaky for training rows only. Validation and test rows use a climatology built from 2023 and earlier.
- 2025 has little usable monsoon data (June to August mostly empty), so monsoon test results rest on few rows.
- Single study district (Kannur), 2019-2025; findings may not transfer to other regions or crops.
- The spatial hold-out covers only 5 blocks of 0.1 degrees (224 points), so "unseen location" results rest on few independent areas. Report block-level intervals and consider block cross-validation.
- 2025 test months with little data: July (344 scorable rows) and August (none); 2024 July has none.
- Only two evaluation years. The gain over climatology was +7.8% in 2024 and about zero in 2025, so year-to-year variability is large. Intervals that resample months (11 clusters) include zero in every set.
- The features at month t cannot see rainfall in month t+1, but an oracle model given next-month rain gained little (Stage 7), so this is not the main reason for the weak 2025 result. The May 2025 and November 2024 failures are unexplained.
- The Random Forest is sensitive to the training window. For the 2025 test, training on 2023-2024 gives +13.6% over an equal-history climatology, but adding 2022 (2022-2024) gives -10.0%. The cause is not known.

## Open items

- ~~Run the July 2022 coverage check.~~ Done 2026-11-03: July 2022 has 99.6% valid points from about one image per point in a month with about 1,370 mm of rain. NDMI (0.23) is in line with June (0.22) and September (0.27); red reflectance is lower (0.051 vs 0.097 in June). No clear contamination, but it is a single-acquisition month, so treat it as low confidence. Optional: list the July 2022 scene dates and cloud percentages in GEE to confirm.
- Decide whether to test neighbourhood averaging for pixel noise (side experiment after Stage 6).
- Optional: test whether 2018 data is usable.
- KVK / Krishibhavan request: not pursued (decision 2026-10-30). Revisit only if the supervisor requires field data.
- Confirm with supervisor: (a) that reference-based validation is acceptable; (b) how the project describes "current stress detection" given that the built system forecasts next-month NDMI; (c) whether the LSTM/GRU promised in Phase 1 is still required or tree models are justified instead.
- Choose one primary model name for the report (RF vs XGBoost tie) and make the saved confusion-matrix figure match.
- ~~Stage 4: lag features and the next-month target.~~ Done 2026-10-31
- ~~Stage 5: train models (Ridge, Random Forest, XGBoost) and evaluate against baselines.~~ Done 2026-10-31, rerun 2026-11-03
- ~~Stage 6: run `src/06_evaluate.py`.~~ Done 2026-11-03, test sets included (see Stage 6 section).
- ~~Rolling-origin evaluation, rain-anomaly diagnostic and oracle ablation.~~ Done 2026-11-03 (Stage 7 section).
- ~~Equal-history comparison.~~ Done 2026-11-03 (Stage 8 section).
- Optional diagnostic: which training year flips the 2025 result (leave-one-year-out), plus a check with several random seeds. Diagnostic only. Do not use it to choose training years by their effect on 2025.
- Look at April-May 2025 directly (actual vs predicted NDMI, timing of the rain within May) to understand the over-prediction. Optional.
- SHAP, ERA5/SMAP cross-check, report figures.
- Discuss with supervisor how to frame the results given the 2024 vs 2025 difference.

## 2026-10-30 - Ground Truth Strategy Update

Note: partly superseded by the 2026-10-31 Label Design Decision. Stress labels from VHI/CWSI are deferred; NDMI classes remain the primary label, and ERA5/SMAP are used for cross-checking only.

### Decision

Not using KVK field data as the primary ground truth.

### Why not KVK

- KVKs mainly hold crop calendars, soil test records and demonstration plot details, not continuous soil-moisture time series.
- Getting data would need official letters, repeated visits and approvals, with an uncertain outcome and timeline.
- Collecting our own field measurements on every Sentinel-2 pass date is not practical within the project schedule.

### Approach

Use public reference/proxy data to validate the models:

- **Moisture reference:** ERA5-Land (primary) and NASA SMAP soil moisture for the Kannur region.
- **Stress labels (deferred):** Vegetation Health Index (VCI/TCI) or a CWSI-style index could be used to create Low/Moderate/High classes.
- **Extra input features:** CHIRPS/IMD rainfall (CHIRPS is already a feature).
- **Optional:** a few spot readings with a low-cost soil moisture sensor as a sanity check. If used, calibrate against oven-dried soil samples and take readings in January to April, when Sentinel-2 coverage is good.

### Limitations

- Reference products are coarse (about 9 km or more) compared to Sentinel-2 (10-20 m), so validation will be at an aggregated regional level, not individual fields.
- These are modelled/proxy values, not direct in-situ measurements, so results show agreement with reference data and not absolute field accuracy.
- Monsoon cloud cover in Kannur creates gaps in optical data. These are handled with a causal climatology fill (Stage 3) and Sentinel-1 radar as an input feature, not with interpolation, which would leak future data.
- Findings may not generalise to other regions or crop types.
- To be confirmed with supervisor that reference-based validation is acceptable.

## 2026-10-31 - Stage 4: What the Feature Table Does and Why

### Purpose

Stage 3 produced `monthly_filled.csv` - one row per (point, month) with gap-filled satellite values.
That format is not usable for forecasting as-is, because a model needs to see _past context_ on the left and _the future outcome_ on the right.
Stage 4 restructures the data into exactly that format:

> **One row = everything known at or before month t -> target is the real NDMI at month t+1.**

### What it builds

| Added column group                                                                | Why                                                                                                                                                                          |
| --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Lag features** (lags 1-3 for NDMI, NDVI, NDWI, rain, soil moisture, VV, VH)     | Gives the model a short memory - recent trends matter for next-month moisture                                                                                                |
| **Cumulative rain** (`rain_sum2`, `rain_sum3`)                                    | Accumulated rainfall over 2-3 months is a stronger drought/stress signal than a single month                                                                                 |
| **NDMI rate of change** (`NDMI_diff1`)                                            | Captures whether vegetation moisture is recovering or declining                                                                                                              |
| **Seasonal signals** (`month_sin`, `month_cos`)                                   | Encodes the time of year smoothly so the model knows it is in monsoon, pre-kharif, etc.                                                                                      |
| **Target columns** (`target_NDMI`, `target_delta`, `target_class_proxy`)          | The thing to predict; uses the **real, unfilled** NDMI only - filled values are never a target                                                                               |
| **Baseline predictions** (`base_persistence`, `base_seasonal_naive`, `base_clim`) | Simple reference forecasts that any ML model must beat to be useful                                                                                                          |
| **Split labels** (`split_time`: train/val/test)                                   | Time-based split so the model always predicts into the future, never the past                                                                                                |
| **Spatial hold-out flag** (`spatial_holdout`)                                     | About 20% of 0.1 degree grid blocks (224 points, about 13% of points) are held back entirely; tests whether the model generalises to unseen locations, not just unseen times |

### Why leakage checks matter

"Data leakage" means accidentally giving the model information it would not have in real deployment (e.g. using next month's rainfall to predict next month's stress).
The script runs seven checks:

1. Target month is exactly one month after the feature month - no off-by-one.
2. `target_NDMI` matches the raw CSV value for the next month - no accidental overwrite.
3. Lag values match the filled values from 1-3 months earlier - shifts are correct.
4. No target column name appears in the feature list.
5. Scrambling all data after June 2024 does not change any feature or baseline for months up to June 2024 - causality holds end-to-end.
6. Train, validation and test do not overlap in target time.
7. Hold-out blocks never appear among the training blocks.

### Scorable rows vs. all rows

All rows are kept (even where `target_valid = 0`) so the table has full context.
Rows with a missing target cannot be used for training, so they are dropped at training time.
**RMSE and classification metrics are computed only on `target_valid == 1` rows** - months where Sentinel-2 actually observed the field.
Filled targets would give artificially smooth errors and hide real model weaknesses.

### What comes next (Stage 5)

Train Ridge regression, Random Forest and XGBoost on the training split and compare their RMSE on scorable val rows against the three baselines.
The spatial hold-out set is kept frozen until a final model is chosen.

## 2026-10-31 - Label Design Decision

### Decision

Keep **`target_NDMI`** (real, unfilled Sentinel-2 NDMI at month t+1) as the primary regression target.
Keep **`target_class_proxy`** (Low / Moderate / High derived from NDMI thresholds) as the primary classification target.
Do **not** replace or supplement these with ERA5-Land soil-moisture percentile classes as a training label.

### Thresholds for target_class_proxy

| Class           | Value | NDMI range      |
| --------------- | ----- | --------------- |
| Low stress      | 0     | NDMI >= 0.2     |
| Moderate stress | 1     | 0 <= NDMI < 0.2 |
| High stress     | 2     | NDMI < 0        |

### Why not ERA5-Land percentile as the label

- `soil_moist` and its lags (1-3 months) are already in the **feature set**.
  Using next-month ERA5-Land soil moisture as the **label** would mean the model learns
  to forecast ERA5 from ERA5 - not to forecast crop stress from satellite imagery.
  This is a data-leakage risk that would produce artificially good RMSE but a useless model.
- ERA5-Land resolution is about 9 km. Labels derived from it would mask the 10-20 m spatial
  variation that Sentinel-2 provides. The 1,721 points fall into only a few dozen ERA5-Land
  cells (exact count to be confirmed), so many points would share the same label regardless of local conditions.
- `target_NDMI` directly answers the project question: will the crop canopy be water-stressed
  next month? ERA5 soil moisture answers a related but different question.

### Why NDMI is the right primary label

- It is the raw, unfilled Sentinel-2 observation - no model output, no proxy index from another product.
- There is no temporal leakage: the target is NDMI at month t+1, while NDMI at month t and its lags are inputs. The model forecasts the next month and does not see it.
- It is at the same spatial scale as the input features (10-20 m).
- It is a well-established index for crop water stress detection in the literature.
- Caveat: the Low/Moderate/High classes are thresholds on this same index, so classification scores measure forecasting of a proxy label, not validated crop stress.

### Role of ERA5-Land in the project

| Use                                    | How                                                                                                                                 |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Input feature                          | `soil_moist` + lags 1-3 already in `features.csv`                                                                                   |
| Cross-check / validation (report only) | After Stage 6, compute ERA5-Land percentile per point on the val/test set and show agreement in a table - **not used for training** |

### Thermal signal (LST / CWSI)

Noted as a possible secondary label but **deferred**. Would require an additional GEE export
(Landsat or MODIS LST). Not worth the time cost before Stage 6 is complete.
Revisit if the NDMI-based model shows weak performance in dry months.

## 2026-10-31 - Reference Data Export Decision (ERA5-Land / SMAP / LST)

### Decision

**Deferred until after model training.** Do not block model training on this export.

### What the export would contain

- ERA5-Land soil moisture layers (volumetric, pixel-level grid across Kannur), including deeper layers
- ERA5-Land skin temperature and 2 m air temperature
- NASA SMAP Level-3 soil moisture (check the GEE catalogue for the current dataset and date coverage)
- Period: 2015-2025 (monthly)

### Why it is not needed before Stage 6

- `features.csv` is already complete - ERA5-Land soil moisture is already sampled at all 1,721 cropland points and is in the feature set.
- This export is **for report validation only** - to show that model predictions agree with an independent reference source. It is not a training input.
- SMAP and LST are not in the current feature set; adding them would require re-running Stage 4, which is not justified unless Stage 6 results are weak.

### Plan

Run the GEE export as a background task in parallel with Stage 6 evaluation (it is small).
Use the output for a cross-check table and map in the report.
If results are weak in dry months, revisit adding skin temperature as an input feature and re-run Stage 4.

## 2026-11-03 - Stage 5: Results (rerun, hold-out excluded from training)

Numbers below are from the corrected rerun (see the correction section further down). Models are trained on 74,948 rows from 1,497 points and scored on the 14,792 scorable 2024 validation rows (target_valid = 1, spatial_holdout = 0).

### Models trained and why these three

| Model                | Why included                                                                                                                           |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Ridge regression** | Linear baseline - shows how much signal is linearly separable. Needs StandardScaler because it is sensitive to feature scale.          |
| **Random Forest**    | Ensemble of decision trees, handles non-linearity and mixed feature types well, robust to outliers, gives feature importance for free. |
| **XGBoost**          | Gradient-boosted trees, often stronger than RF on tabular data, handles NaN natively, faster to tune.                                  |

Both RF and XGBoost were run for regression (predict `target_NDMI`) and classification (predict `target_class_proxy`: Low / Moderate / High stress). Hyperparameters have not been tuned.

### Regression results (val, 14,792 rows)

| Model               | RMSE       | MAE        | R2         | RMSE vs climatology |
| ------------------- | ---------- | ---------- | ---------- | ------------------- |
| base_persistence    | 0.1320     | 0.0909     | 0.5222     | worse               |
| base_seasonal_naive | 0.0989     | 0.0706     | 0.7315     | worse               |
| base_clim           | 0.0933     | 0.0705     | 0.7610     | -                   |
| Ridge               | 0.1077     | 0.0836     | 0.6818     | worse               |
| **Random Forest**   | **0.0860** | **0.0637** | **0.7970** | -7.8%               |
| XGBoost             | 0.0874     | 0.0649     | 0.7906     | -6.3%               |

Random Forest beats the best baseline (climatology) by 7.8% RMSE (9.6% MAE). Ridge fails to beat any baseline except persistence. Persistence is the weakest forecaster, consistent with the Stage 3 gap-fill result. Confidence intervals are still to be computed (Stage 6).

### Classification results (val, 14,792 rows)

| Method              | Accuracy | wF1    | F1 Low | F1 Moderate | F1 High |
| ------------------- | -------- | ------ | ------ | ----------- | ------- |
| base_majority_class | 0.4302   | 0.2588 | 0.602  | 0.000       | 0.000   |
| base_persistence    | 0.6937   | 0.6918 | 0.783  | 0.527       | 0.718   |
| base_seasonal_naive | 0.7622   | 0.7625 | 0.826  | 0.606       | 0.822   |
| base_clim           | 0.7543   | 0.7602 | 0.823  | 0.614       | 0.812   |
| Random Forest       | 0.7841   | 0.7802 | 0.848  | 0.620       | 0.837   |
| XGBoost             | 0.7824   | 0.7814 | 0.846  | 0.634       | 0.831   |

The models are about 9 points of accuracy above persistence but only about 2-3 points above seasonal-naive and climatology. Moderate stress is the hardest class (F1 about 0.62-0.63, only 0.006-0.028 above the baselines); it is a transitional class with NDMI values near the thresholds (0 and 0.2). Most of the classification skill comes from seasonality. RF and XGBoost are a tie (XGBoost has marginally higher weighted F1 here, so the saved confusion-matrix figure shows XGBoost).

### Top-10 features (Random Forest regressor, impurity importance)

| Rank | Feature        | Importance |
| ---- | -------------- | ---------- |
| 1    | NDMI_fill      | 0.313      |
| 2    | rain_sum3      | 0.123      |
| 3    | rain_mm        | 0.080      |
| 4    | rain_sum2      | 0.079      |
| 5    | rain_mm_lag1   | 0.074      |
| 6    | NDMI_fill_lag1 | 0.032      |
| 7    | NDVI_fill      | 0.029      |
| 8    | NDMI_diff1     | 0.024      |
| 9    | month_cos      | 0.019      |
| 10   | NDWI_fill      | 0.015      |

Current NDMI (about 31%) is the strongest single predictor. The four rainfall features together carry about 36%. Impurity importance splits credit among correlated features and is biased, so do not claim that rainfall "drives" stress from this table alone; confirm with the Stage 6 ablations, permutation importance and SHAP.

### Model chosen going forward

**Random Forest** is kept as the primary model: it is marginally better on regression RMSE, a tie on classification, and easy to interpret. The difference to XGBoost (0.0860 vs 0.0874 RMSE) is small and should not be presented as a clear win.

### What the spatial hold-out is for

224 points in about 20% of the 0.1 degree grid blocks are excluded from training and validation (true for the rerun; see the correction below for the first run).
They are scored in Stage 6 to test whether the model **generalises to completely unseen locations** - a stricter test than time-based validation alone.

### What comes next (Stage 6)

- Run `src/06_evaluate.py`: scores on seen and unseen points, bootstrap intervals, error by month, feature-group ablations. Validation first (`EVALUATE_TEST = False`), then 2025 once.
- Run **SHAP** on the RF regressor.
- Produce the **ERA5/SMAP cross-check table** using the deferred GEE export.
- Final report figures: feature importance, SHAP summary, predicted vs actual map.

## 2026-11-03 - Correction: hold-out points were in training in the first Stage 5 run

### What happened

The first version of `05_train.py` selected training rows with `split_time == "train"` only. The 224 spatial hold-out points were therefore in the training data (86,203 train rows from all 1,721 points), although this log stated they were never seen during training. This was found by reading the script; the row count matched all points (91,366 scorable train rows minus 5,163 rows without full lags = 86,203).

### Effect

- Validation scores were not materially affected, because validation rows already excluded the hold-out points.
- A Stage 6 hold-out test on the first-run models would have been invalid (the model would already know those locations).

### Fix

Training now filters on `split_time == "train"` and `spatial_holdout == 0`, with an assertion in the script. Rerun: 74,948 train rows from 1,497 points.

### First run vs rerun (val, 14,792 scorable rows)

| Metric                 | First run       | Rerun           |
| ---------------------- | --------------- | --------------- |
| Ridge RMSE             | 0.1075          | 0.1077          |
| Random Forest RMSE     | 0.0862          | 0.0860          |
| XGBoost RMSE           | 0.0872          | 0.0874          |
| RF accuracy / wF1      | 0.7843 / 0.7806 | 0.7841 / 0.7802 |
| XGBoost accuracy / wF1 | 0.7794 / 0.7781 | 0.7824 / 0.7814 |

### Other fixes made at the same time

- Classification baselines (persistence, seasonal-naive, climatology, most-common-class) were added; previously accuracy had no reference point.
- The saved confusion matrix was hard-coded to XGBoost; it now plots the classifier with the higher weighted F1.
- The first-run classification table in this log listed XGBoost F1 High as 0.837; the script output was 0.829. Corrected.
- Corrected wording elsewhere in this log: NDMI at month t and its lags are features (only the next-month NDMI is the target); the points do not all lie in one ERA5-Land cell; the hold-out is 20% of blocks (about 13% of points); gap handling uses a causal fill and not interpolation; the four rainfall features carry about 36% of RF importance.

## 2026-11-03 - Stage 6: first full evaluation (validation and test)

The script default was `EVALUATE_TEST = True`, so the 2025 test sets were scored in the first run. They must not be used to tune models. Seen = training-area points, unseen = spatial hold-out points (5 blocks). All rows are scorable (real next-month observation).

### Regression RMSE

| Set                | n      | Persistence | Seasonal naive | Climatology | Random Forest | XGBoost |
| ------------------ | ------ | ----------- | -------------- | ----------- | ------------- | ------- |
| val_seen (2024)    | 14,792 | 0.1320      | 0.0989         | 0.0933      | 0.0860        | 0.0874  |
| val_unseen (2024)  | 2,116  | 0.1105      | 0.0915         | 0.0868      | 0.0829        | 0.0838  |
| test_seen (2025)   | 13,654 | 0.1235      | 0.1077         | 0.0971      | 0.0984        | 0.0982  |
| test_unseen (2025) | 1,952  | 0.1030      | 0.1009         | 0.0865      | 0.0847        | 0.0857  |

### Random Forest RMSE gain vs climatology (%), median [95% interval]

| Set         | Resample points   | Resample months     | Resample blocks    |
| ----------- | ----------------- | ------------------- | ------------------ |
| val_seen    | +7.8 [+6.1, +9.5] | +8.3 [-10.4, +22.6] | +7.9 [+3.8, +10.4] |
| val_unseen  | +4.6 [-0.0, +8.4] | +3.0 [-19.0, +21.0] | +4.5 [-8.7, +14.8] |
| test_seen   | -1.3 [-3.8, +1.0] | -1.1 [-21.9, +16.1] | -1.4 [-6.1, +2.6]  |
| test_unseen | +2.1 [-5.2, +8.0] | +2.6 [-22.1, +18.1] | +2.1 [-0.6, +5.8]  |

Resampling points alone is too optimistic because all points share each month's weather. Month-level intervals (11 clusters) are very wide and include zero everywhere.

### Classification accuracy

| Set         | Persistence | Seasonal naive | Climatology | Random Forest | XGBoost |
| ----------- | ----------- | -------------- | ----------- | ------------- | ------- |
| val_seen    | 0.694       | 0.762          | 0.754       | 0.784         | 0.782   |
| val_unseen  | 0.730       | 0.774          | 0.773       | 0.796         | 0.791   |
| test_seen   | 0.677       | 0.725          | 0.719       | 0.711         | 0.709   |
| test_unseen | 0.731       | 0.745          | 0.755       | 0.733         | 0.736   |

On 2025 the models are below the seasonal and climatology baselines (test_seen accuracy gain vs seasonal naive -1.5 points, interval by points [-2.4, -0.5]).

### Error by target month (seen points, RMSE: Random Forest vs climatology)

Random Forest is better than climatology in 9 of 11 scored months in 2024 and 5 of 11 in 2025. Largest failures: November 2024 (0.123 vs 0.082) and May 2025 (0.156 vs 0.097). May 2025 had the highest May rainfall in the dataset (mean 682 mm against 98-421 mm in other years). The rain explanation was tested in Stage 7 and is not supported (oracle with next-month rain gained little; the error had the opposite sign to the rain anomaly). Both months remain unexplained.

### Ablations (RF retrained, 150 trees, val_seen; climatology RMSE 0.0933)

| Configuration         | Features | RMSE   | Gain vs climatology |
| --------------------- | -------- | ------ | ------------------- |
| All features          | 38       | 0.0869 | +6.8%               |
| Without rain          | 32       | 0.0906 | +3.0%               |
| Without optical       | 25       | 0.1273 | -36.4%              |
| Without soil moisture | 34       | 0.0873 | +6.4%               |
| Without radar         | 30       | 0.0883 | +5.4%               |
| Without season        | 36       | 0.0871 | +6.7%               |
| Without quality flags | 33       | 0.0870 | +6.8%               |
| Rain + season only    | 8        | 0.1508 | -61.6%              |
| Optical + season only | 15       | 0.0989 | -6.0%               |

### Reading of the results (as of this run)

- Current and lagged optical indices are essential: they carry both the current state and the identity of each point. The "rain + season only" model has no point-specific information, so it is not a fair "no satellite" test.
- Optical features alone (with season) do not beat climatology. The gain over climatology comes from combining them with rainfall (about 3.8 points) and some from radar (about 1.4 points). Soil moisture, season and quality flags add nothing measurable (differences of 0.0002-0.0004 RMSE are within noise; single seed).
- Unseen locations score about as well as seen locations, so there is no sign of spatial overfitting, but the unseen set is only 5 blocks and its intervals are wide.
- The improvement over climatology seen in 2024 did not repeat in 2025. With two evaluation years, no reliable improvement can be claimed.

## 2026-11-03 - Stage 7: rolling-origin evaluation and diagnostics

For each test year the models are trained on rows whose target month is before that year (hold-out points excluded), and the climatology baseline is recomputed from earlier years only. Seen points, scorable rows. Folds use 2, 3, 4, 5 and 6 years of history respectively.

### RMSE by test year

| Test year | Rows   | Persistence | Seasonal naive | Climatology | Random Forest | XGBoost | Blend (exploratory) | Oracle |
| --------- | ------ | ----------- | -------------- | ----------- | ------------- | ------- | ------------------- | ------ |
| 2021      | 17,202 | 0.1382      | 0.1170         | 0.1237      | 0.0934        | 0.0940  | 0.0947              | 0.0928 |
| 2022      | 15,103 | 0.1333      | 0.1229         | 0.1207      | 0.0951        | 0.0941  | 0.0967              | 0.0942 |
| 2023      | 15,192 | 0.1331      | 0.1440         | 0.1054      | 0.0927        | 0.0924  | 0.0892              | 0.0903 |
| 2024      | 14,792 | 0.1320      | 0.0989         | 0.0933      | 0.0860        | 0.0874  | 0.0796              | 0.0890 |
| 2025      | 13,654 | 0.1235      | 0.1077         | 0.0930      | 0.0975        | 0.0987  | 0.0819              | 0.0934 |

### Gain vs climatology (RMSE, %)

| Test year | RF    | XGBoost | Blend | Oracle | RF on rows with a real current-month input | Months RF better |
| --------- | ----- | ------- | ----- | ------ | ------------------------------------------ | ---------------- |
| 2021      | +24.5 | +24.0   | +23.4 | +25.0  | +25.0                                      | 9/12             |
| 2022      | +21.2 | +22.0   | +19.8 | +21.9  | +24.4                                      | 8/11             |
| 2023      | +12.1 | +12.3   | +15.4 | +14.3  | +13.2                                      | 8/12             |
| 2024      | +7.8  | +6.4    | +14.7 | +4.7   | +7.6                                       | 9/11             |
| 2025      | -4.8  | -6.1    | +11.9 | -0.3   | -3.7                                       | 5/11             |

### Class accuracy (thresholded predictions)

| Test year | Persistence | Seasonal naive | Climatology | RF    | Blend |
| --------- | ----------- | -------------- | ----------- | ----- | ----- |
| 2021      | 0.626       | 0.680          | 0.664       | 0.735 | 0.721 |
| 2022      | 0.613       | 0.657          | 0.658       | 0.703 | 0.705 |
| 2023      | 0.691       | 0.642          | 0.729       | 0.768 | 0.792 |
| 2024      | 0.694       | 0.762          | 0.754       | 0.780 | 0.796 |
| 2025      | 0.677       | 0.725          | 0.733       | 0.702 | 0.759 |

### Pooled over all folds (RF RMSE gain vs climatology, %, median [95% interval])

Seen points: +14.1 [+4.7, +22.0] (resampling 57 year-months), +14.5 [+12.2, +16.5] (21 blocks). Unseen points: +14.9 [+5.2, +23.5] (year-months), +15.1 [+0.9, +18.9] (5 blocks). These pooled numbers are dominated by the early folds and should not be quoted as the model's expected gain (see below).

### Reading of the results

- The RF error is roughly constant across years (0.086-0.098) while the climatology error falls as it gains history (0.124 with 2 years, 0.093 with 6 years). The shrinking gain therefore mostly reflects a better baseline. With 5-6 years of history, climatology is hard to beat: +7.8% in 2024 and -4.8% in 2025. The idea that the model reaches climatology-level accuracy with far less history (data efficiency) was tested in Stage 8 and is only partly supported.
- The fill-leak sensitivity check (rows with a real current-month input) gives almost the same gains, so the Stage 3 fills are not driving these results. Unseen points do as well as seen points.
- Oracle: giving the model next-month rain changes little (2024: +4.7 vs +7.8 for the normal model; 2025: -0.3 vs -4.8). Not knowing future rain is not the main limit.
- Diagnostic A (57 year-months): the correlation of RF bias with next-month rain anomaly is +0.20 (Pearson) and +0.05 (Spearman), the opposite sign to the hypothesis and weak. In May 2025 the model over-predicted NDMI by 0.128 in a month that was 409 mm wetter than normal; the oracle error (0.131) was still far above climatology (0.098). November 2024 (RF 0.123 vs 0.082, oracle 0.123, rain anomaly -52 mm) is also unexplained.
- The 50/50 blend with climatology beats climatology in 2023-2025 on RMSE (+15.4, +14.7, +11.9%) and in every fold on class accuracy (+5.7, +4.7, +6.3, +4.2, +2.6 points). It was proposed after seeing the Stage 6 results, so the 2024 and 2025 results are not a clean test; 2021-2022 were not used to motivate it, and there the blend is about equal to or slightly worse than RF.

## 2026-11-03 - Stage 8: equal-history comparison

For each test year and history length, the Random Forest is trained only on the target months of the H years before the test year (hold-out points excluded) and the climatology is built from the same H years. "All" means every year before the test year. Seen points, scorable rows, one seed (42). The blend (50/50 RF and climatology) is exploratory.

### RF gain vs equal-history climatology (RMSE, %)

| Test year | 1 yr  | 2 yrs | 3 yrs | 4 yrs | 5 yrs | all   |
| --------- | ----- | ----- | ----- | ----- | ----- | ----- |
| 2021      | +17.0 | +24.5 | -     | -     | -     | +24.5 |
| 2022      | +17.0 | +14.8 | +21.2 | -     | -     | +21.2 |
| 2023      | +32.6 | +28.3 | +23.9 | +12.1 | -     | +12.1 |
| 2024      | +10.1 | +16.0 | +14.2 | +10.1 | +7.8  | +7.8  |
| 2025      | +14.9 | +13.6 | -10.0 | -10.7 | -10.5 | -4.8  |

### Blend gain vs equal-history climatology (RMSE, %, exploratory)

| Test year | 1 yr  | 2 yrs | 3 yrs | 4 yrs | 5 yrs | all   |
| --------- | ----- | ----- | ----- | ----- | ----- | ----- |
| 2021      | +19.9 | +23.4 | -     | -     | -     | +23.4 |
| 2022      | +18.2 | +16.4 | +19.8 | -     | -     | +19.8 |
| 2023      | +25.3 | +22.4 | +20.3 | +15.4 | -     | +15.4 |
| 2024      | +18.1 | +19.1 | +17.8 | +15.6 | +14.7 | +14.7 |
| 2025      | +19.9 | +20.3 | +10.2 | +7.8  | +8.3  | +11.9 |

### Test years 2024 and 2025 pooled (identical rows for every history length, 28,446 rows)

| History | Climatology RMSE | RF RMSE | Blend RMSE | RF gain, resampling year-months | RF gain, resampling blocks | Blend gain, resampling year-months |
| ------- | ---------------- | ------- | ---------- | ------------------------------- | -------------------------- | ---------------------------------- |
| 1 yr    | 0.1047           | 0.0916  | 0.0847     | +11.5 [-1.2, +24.0]             | +12.1 [+9.2, +15.4]        | +19.0 [+13.4, +24.1]               |
| 2 yrs   | 0.1058           | 0.0902  | 0.0850     | +14.0 [-0.8, +27.3]             | +14.9 [+12.5, +16.9]       | +19.7 [+12.3, +26.3]               |
| 3 yrs   | 0.0971           | 0.0942  | 0.0830     | +2.6 [-15.0, +20.6]             | +2.7 [-1.0, +7.0]          | +14.3 [+7.3, +20.6]                |
| 4 yrs   | 0.0935           | 0.0932  | 0.0822     | +0.4 [-15.6, +15.1]             | +0.3 [-2.6, +3.0]          | +11.9 [+5.3, +17.6]                |
| 5 yrs   | 0.0918           | 0.0928  | 0.0810     | -0.9 [-17.3, +11.8]             | -1.1 [-4.5, +1.8]          | +11.8 [+6.3, +16.3]                |
| all     | 0.0932           | 0.0917  | 0.0807     | +1.9 [-12.8, +13.0]             | +1.6 [-1.6, +4.4]          | +13.4 [+9.2, +17.2]                |

### Random Forest with short history vs climatology from all history (2024-2025 pooled)

| RF history | RF RMSE | Climatology (all history) RMSE | Gain  | 2024  | 2025  | Interval (year-months) |
| ---------- | ------- | ------------------------------ | ----- | ----- | ----- | ---------------------- |
| 1 yr       | 0.092   | 0.093                          | +1.7% | +3.0% | +0.3% | [-8.8, +11.0]          |
| 2 yrs      | 0.090   | 0.093                          | +3.5% | +5.3% | +1.1% | [-7.9, +11.7]          |
| 3 yrs      | 0.094   | 0.093                          | -1.1% | +6.8% | -9.0% | [-17.3, +13.3]         |

### Reading of the results

- With 1-2 years of history the RF beats an equally short climatology by about 12-14% (pooled), and with 3 or more years the pooled gain falls to about zero. This fits the data-efficiency idea, but the pooled drop is driven by 2025. In 2024 the RF stays ahead at every history length (+7.8 to +16.0%). All year-month intervals for the RF gain include zero, so the pattern is not statistically established.
- The data-efficiency claim that survives: an RF trained on 1-2 years is about as accurate as a climatology built from all 5-6 earlier years (+1.7% and +3.5%, intervals include zero). It matches the long climatology; it does not clearly beat it.
- The RF is unstable with respect to the training window. For 2025, adding 2022 to the training years moves the gain from +13.6% to -10.0%. The cause is not known. Do not choose training years by their effect on 2025.
- The blend is ahead of the equal-history climatology in all 24 cells (+7.8% to +25.3%) and its pooled year-month intervals exclude zero at every history length. In the folds that were not used to motivate it (2021-2023) it is similar to the RF, and its main advantage is robustness in 2025. It remains exploratory because it was proposed after seeing the Stage 6 results.
