# Automated Crop Moisture/Stress Detection and Prediction (Kannur)

Group 13, Dept. of CSE, Government College of Engineering Kannur
Supervisor: Prof. Amrithasree Haridas

Detect current crop moisture stress and predict next-month stress for
Kannur district using Sentinel-2 / Sentinel-1, CHIRPS and ERA5-Land data
from Google Earth Engine.

## Structure
- `gee/`          Earth Engine JavaScript scripts (copy of what runs in the Code Editor)
- `data/raw/`     CSVs exported from GEE (not tracked by git; shared via Drive)
- `data/processed/` cleaned, gap-filled and feature tables (not tracked)
- `notebooks/`    exploration and experiments
- `src/`          reusable Python code (loading, features, models)
- `dashboard/`    Streamlit app
- `results/`      figures and tables used in the report
- `report/`       report and presentation sources

## Workflow rules
1. One branch per task, merge via pull request (one reviewer).
2. Never commit raw data. Share it through the team Drive folder.
3. Every GEE export and every experiment gets an entry in LOG.md.
4. Fixed random seed = 42 everywhere.
5. Never tune on the test set. Say which labels any number was computed on.
