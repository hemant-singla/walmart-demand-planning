# Source dictionary

## External sources

| Source | What | Where it is used |
|---|---|---|
| M5 Forecasting competition (Kaggle 2020), Zenodo record 10203108 | Walmart unit sales, calendar, weekly prices; 30,490 product-store series, 10 stores (CA, TX, WI), 29 Jan 2011 – 22 May 2016 | All analysis |
| `data/source_manifest.json` | Download URLs, timestamps, MD5 and SHA-256 of the three raw files | Re-verified on the user's machine (3/3 match) |

Raw files stay local in `data/raw/` and are excluded from Git, because redistribution terms were not established. Only aggregates and the fixed 200-series panel are written elsewhere.

## Raw files (`data/raw/`, not committed)

| File | Grain | Key columns |
|---|---|---|
| `sales_train_evaluation.csv` | 1 row per series, 1,941 daily columns `d_1..d_1941` | `id, item_id, dept_id, cat_id, store_id, state_id` |
| `calendar.csv` | 1 row per day (`d_1..d_1969`) | `date, wm_yr_wk, weekday, wday, month, year, d, event_name_1/2, event_type_1/2, snap_CA, snap_TX, snap_WI` |
| `sell_prices.csv` | store × item × week | `store_id, item_id, wm_yr_wk, sell_price` |

## Prepared files (`data/prepared/`, built by `scripts/prepare_data.py`)

| File | Content |
|---|---|
| `panel_metadata.csv` | The 200 panel series with selection statistics from d_1–d_730: `selection_units`, `selection_nonzero_days`, `selection_zero_share`, `volume_group`, `pattern_group`, `stratum`, `pilot` |
| `sales_panel.csv` / `sales_pilot.csv` | Wide daily sales for the panel (200) and the pilot (30) |
| `daily_sales.csv.gz` / `daily_sales_pilot.csv.gz` | The same sales in long format, `id × d`. This is the same data in another layout, not extra observations |
| `sell_prices_panel.csv` / `_pilot.csv` | Weekly prices for panel items |
| `calendar.csv` | Copy of the raw calendar |

## Derived data (DuckDB, `sql/`)

| Table / file | Built by | Grain | Notes |
|---|---|---|---|
| `observed_history` | `01_load_audit.sql` | id × day | Sales + calendar + same-week price. Retrospective only; Python lags price to the last completed week before each forecast date |
| `audit_checks` → `results/checkpoint1/sql_audit*.csv` | `01_load_audit.sql` | 1 row | Keys, totals, wide-vs-long and join checks |
| `data/derived/model_input*.csv.gz` | `01_load_audit.sql` | id × day | Python's model input; missing prices kept missing |
| `results/analytics/sql_*.csv` | `02_analytics.sql` | model × segment, rule × K | Independent recomputation of WAPE, bias, RMSSE and list scores |
| `results/dashboard/ctx_*.csv` | `03_business_context.sql` | various | Company-wide aggregates from the full raw sales file (see below) |

### Business-context tables (`results/dashboard/ctx_*.csv`)

| File | Grain | Columns |
|---|---|---|
| `ctx_guard` | 1 row | rows, series, stores, days, total units in the raw file |
| `ctx_daily_store_cat` | day × store × category | units, items_selling |
| `ctx_store_summary` | store | series, total_units, share_of_units, zero_share_after_launch, avg daily units 2012/2015, growth |
| `ctx_dept_summary` | department | series, items, units, share, zero share, avg units per series-day |
| `ctx_monthly` | month × state × category | avg_daily_units |
| `ctx_weekday` | weekday × state × category | avg_daily_units, index_vs_week (week average = 100) |
| `ctx_snap` | state × category | avg daily units on SNAP vs other days (2012–2015), difference. An association, not a causal effect |
| `ctx_events` | event | event-day units vs the same weekday ±1–4 weeks. An association |
| `ctx_pareto` | series rank | cumulative share of units |
| `ctx_zero_share` | category × 10% bin | number of series by share of zero-sales days after launch |
| `ctx_panel_vs_m5` | population | all M5 vs sampling universe vs our panel |
| `ctx_price_changes` | store (panel items) | share of item-weeks with a price change or cut |

"After launch" means from each series' first recorded sale onward.

## Model and evaluation results (`results/`)

| Path | Content |
|---|---|
| `checkpoint1/` | Reconciliation checks (26), audit JSON |
| `checkpoint2/` | Pilot forecasts, metrics, runtime, test log, manual metric check |
| `checkpoint3/` | Tuning metrics, model choice, validation metrics (overall, segment), interval coverage, runtime |
| `backtest/origins/<T>.csv.gz` | Every forecast from weekly origins 1493–1906: `model, origin, idx, h, d, forecast, y, scale, mae_scale` (actuals after d_1913 sealed) |
| `backtest/intervals_lgbm.csv.gz` | 90% ranges for LightGBM forecasts, origins 1584–1906 |
| `checkpoint4/` | Priority signals, weekly results for every rule and weight combination, summary, frozen-choice record |
| `holdout/` | Final-28-day forecasts, metrics, ranges, weekly lists, signals; `crosscheck_windows_lgbm_1913.csv.gz` is the user's laptop LightGBM run, used for the cross-platform comparison |
| `analytics/` | SQL recomputation and the SQL-vs-Python reconciliation |
| `dashboard/` | Tables feeding Power BI, plus `dashboard_reconciliation.csv` (351/351 checks) |

## Key definitions

| Term | Definition |
|---|---|
| Origin `T` | Forecast date. Data `d_1..d_T` known; forecasts for `d_T+1..d_T+28`. Always a Sunday |
| RMSSE | `sqrt(mean_h (y−f)² / mean((Δy)²))`, where the scale uses history up to `T` from the first sale. Undefined if the scale is 0 |
| WAPE | `Σ|y−f| / Σy`. Undefined if `Σy = 0` |
| Bias | `Σ(f−y) / Σy`. Negative means under-forecast |
| Captured share | A list's share of all 200 series' absolute unit error over the next 7 days |
| Normalised error | 7-day absolute error ÷ (7 × mean absolute daily change) |
| Large-error event | Normalised error > 1.442, the 90th percentile on calibration weeks |
| `idx` | 0-based position of a series in `panel_metadata.csv` sorted by `id` |

## Power BI project (`powerbi/`)

`build_pbip.py` copies `results/dashboard` into `powerbi/data/` with friendly labels. It then writes the project: a TMDL data model (23 tables, 8 relationships, 35 measures) and a PBIR report (10 pages). The `DataFolder` parameter must point at `powerbi\data\`.
