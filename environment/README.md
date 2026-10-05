# Environments that produced the results

| Step | Machine | Versions |
|---|---|---|
| Checkpoints 1-3, holdout rerun (checkpoint 4b), SQL 02/03, dashboard tables, Power BI project | Claude cloud workspace, Linux, Python 3.13.16 | pandas 3.0.5, numpy 2.5.3, lightgbm 4.6.0 (official wheel), DuckDB CLI 1.4.1 (`executed_versions.json`) |
| Priority experiment + freeze (checkpoint 4a), first holdout attempt, SQL 01 | User's Windows laptop, Python 3.14.4 | `requirements-lock-windows.txt` (lightgbm 4.7.0, duckdb 1.5.6, pandas 2.3.3) |

The package index was blocked in the cloud workspace, so statsmodels and Streamlit were never installed there.
LightGBM forecasts differ slightly between the two machines (holdout RMSSE 0.7339 vs 0.7333; see PROGRESS.md). Install `lightgbm==4.6.0` to match the reported numbers.
