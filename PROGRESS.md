# PROGRESS

## Checkpoint 1 — data audit, SQL tables, environment: COMPLETE
- Raw source SHA-256 re-verified on the user's machine against data/source_manifest.json: all 3 match.
- `sql/01_load_audit.sql` executed in DuckDB (CLI v1.4.1) for pilot and panel: 26/26 reconciliation checks pass
  (results/checkpoint1/reconciliation_checks.csv): 388,200 rows = 200 x 1941, 865,515 units = audit, no duplicate
  id/day or store/item/week keys, wide == long cell by cell, joins preserve rows and units, 22,253 missing-price days
  = audit, 0 positive-sale days without price.
- All 22,253 missing-price days fall before each item's first priced week (83 series); none after launch.
- Date windows fixed before modeling: config/windows.json.
- Environment blocker (worked around): package index (PyPI) blocked in both execution environments.
  LightGBM 4.6.0 installed from its official GitHub wheel; DuckDB run via official CLI binary; statsmodels and
  Streamlit could not be installed -> ETS implemented in numpy (src/wdp/models.py); Streamlit app cannot be run here.

## Checkpoint 2 — pilot (30 series) and temporal validation: COMPLETE
- tests/test_temporal.py 7/7 pass (seal of final 28 days, features invariant to scrambled future sales/prices,
  LightGBM training targets <= origin, seasonal-naive equivalence + weekday alignment, ETS toy recovery,
  metric zero/undefined denominators, disjoint weekly evaluation windows). Test caught & fixed an ETS AIC bug (SSE=0).
- Pilot origins 1773/1829/1885 (28-day), mean RMSSE / WAPE / bias:
  ETS 0.630 / 0.626 / -2.3%; LightGBM (tweedie_31, untuned) 0.633 / 0.620 / -8.1%; seasonal naive 0.821 / 0.745 / -4.5%.
- Manual recomputation of one seasonal-naive RMSSE and the ETS WAPE matches pipeline exactly.
- Runtime: LightGBM ~3.2 s/fit on 30 series; ETS 0.01 s/origin.
- Pilot is too small to rank ETS vs LightGBM; decision deferred to 200-series validation.

## Checkpoint 3 — 200-series forecast comparison and intervals: COMPLETE
- Limited LightGBM tuning (3 configs, tuning origins 1661/1689/1717 only, fixed rounds, no early stopping):
  tweedie_63 0.658 < tweedie_31 0.662 < poisson_31 0.664 mean RMSSE -> tweedie_63 frozen (results/checkpoint3/lgbm_choice.json).
- Weekly rolling backtest, origins 1493..1906 step 7 (60 origins), LightGBM refit every origin with targets <= origin,
  actuals after d_1913 sealed: results/backtest/origins/<origin>.csv.gz (+ runtime). 0 model failures, 0 ETS fallbacks.
- 28-day comparison on 6 validation origins (1745..1885), 200 series:
  | model | mean RMSSE | median RMSSE | WAPE | bias |
  | LightGBM | 0.674 | 0.629 | 0.605 | -5.8% |
  | ETS | 0.688 | 0.644 | 0.626 | -1.1% |
  | seasonal naive | 0.889 | 0.865 | 0.754 | -2.3% |
  LightGBM best at 6/6 origins, but margin over ETS is small (paired mean RMSSE diff -0.014; LightGBM better on 57%
  of series-origins). LightGBM under-forecasts more (-5.8% bias, -6% on high/medium volume); ETS nearly unbiased.
  Low-volume segment: LightGBM 0.595 vs ETS 0.598 (essentially tied). Runtime: LightGBM ~25 s/origin, ETS 0.05 s.
- Pre-registered rule -> primary forecast model = LightGBM (results/checkpoint3/forecast_choice.json).
- 90% empirical intervals from past out-of-sample errors (26-week pools, per series x horizon week). Raw calibration
  coverage 0.84-0.87 (too narrow) -> width multipliers 1.05/1.10/1.10/1.15 fixed on calibration origins (outcomes <= d_1668).
  Validation coverage 0.909 overall (28-day), 0.904 weekly h1-7; by segment 0.90-0.92; widens with horizon (0.898 -> 0.921).
- Holdout (d_1914-1941) not yet touched.

## Checkpoint 4 — priority experiment, freeze, final holdout: COMPLETE
- `checkpoint4_priority.py` run by the user on Windows (2026-10-04 16:54 UTC) -> config/frozen_choices.json
  (sha256 0a084296...). Event threshold (90th pct normalised 7-day error, calibration weeks) = 1.442.
- Validation, 35 weekly lists (origins 1668-1906), K=5, share of next-7-day absolute unit error captured:
  proposed (median-normalised, weights recent_error 0.2 / bias 0.1 / uncertainty 0.7) 16.4%; uncertainty alone 16.1%;
  recent_error 16.0%; volume 15.6%; bias 13.9%; random 2.5% (p10-p90 1.2-4.1%). Proposed beat recent_error in 18/35
  weeks (9 ties), volume in 21/35. Split check (weights chosen on first half, scored on second) passed narrowly:
  17.04% vs 16.98% volume. Per the pre-registered rule the proposed score was recommended, but margins are ~0.5 pp.
- Normalised-error events: unit-ranked lists have precision@5 of 8-13% (random 9%) -> they find big-unit errors,
  dominated by volume, not unusually bad forecasts. Diagnostic list ranked by normalised recent error: precision@5 60%,
  recall@5 18% but captures only 3.9% of unit error. The two goals need different lists.
- Holdout first run on Windows crashed: LightGBM at weekly origins 1920/1927/1934 raised IndexError because calendar
  arrays stopped at d_1941 while 28-day windows extend to d_1962. Fixed in src/wdp/data.py (full calendar d_1-d_1969,
  SNAP cross-checked), regression test added (8/8 tests pass), holdout script now aborts loudly on model failures.
  Frozen choices unchanged. Pre-holdout results unaffected (all ended <= d_1934). Holdout rerun in the Claude workspace.
- Holdout 28-day forecast (origin 1913, days 1914-1941), mean RMSSE / WAPE / bias:
  LightGBM 0.733 / 57.9% / -4.9%; ETS 0.746 / 58.6% / -6.8%; seasonal naive 0.932 / 68.0% / -10.6%.
  LightGBM lowest in every segment, but by 0.002-0.025 RMSSE over ETS; low-volume tied (0.682 vs 0.684).
  All models under-forecast in the holdout; low-volume bias -15% (LightGBM).
- Holdout 90% intervals: coverage 0.893 (28-day), 0.889 weekly h1-7; weakest irregular 0.877, FOODS 0.881.
- Holdout weekly lists (4 weeks only, 15-25 events/week), K=5 captured unit error: proposed 13.4%, volume 13.0%,
  recent_error 12.8%, uncertainty 12.8%, bias 8.6%, random 2.5%. Proposed best in 2 of 4 weeks; differences are
  within week-to-week noise. Precision@5: recent_error 25%, proposed 15%, volume 10%.
- Cross-platform check: LightGBM holdout forecasts differ between the Windows run and the Linux rerun (mean abs
  diff 0.07 units, max 5.2, corr 0.9993; RMSSE 0.7339 vs 0.7333). ETS and seasonal naive identical.
- SQL recomputation (sql/02_analytics.sql) reconciles with Python: 60 forecast-metric rows, 36 priority rows, 0 mismatches.

## Checkpoint 5 — dashboard, memo, README, interview material: COMPLETE
- User chose Power BI instead of Streamlit (one dashboard). No Streamlit app built.
- scripts/build_dashboard_data.py run: results/dashboard/* (plain CSV); dashboard-vs-results reconciliation 351/351 pass.
- sql/03_business_context.sql run in DuckDB on the FULL raw sales file (59,181,090 series-days, 30,490 series, 10 stores,
  66,927,173 units; guard table matches). Company context: FOODS 68.6% of units; CA_3 17.0% of units; top 10% of series
  = 55% of units; zero-sales share after launch 59.5%; weekend index ~120-123; FOODS on SNAP days +10.5% CA, +15.5% TX,
  +30.8% WI (association); Christmas -99.9% (closed). Panel is busier than M5 (2.37 vs 1.43 units/series-day).
- Failure case found for memo: FOODS_3_444_CA_1 (333 zero days while priced, then 414 units vs forecast 3; ranked
  193-199/200 by every rule); FOODS_1_043_TX_1 similar (76 zero days). Top 10 series = 26.6% of holdout abs error.
- powerbi/build_pbip.py generates a Power BI project (PBIP: TMDL model + PBIR report): 23 tables, 8 relationships,
  35 measures, 10 pages, 69 visuals. All 82 report JSON files pass Microsoft's official JSON schemas (validator proven
  to catch injected errors); every visual/measure field reference and relationship key checked (0 problems).
  Opened in the user's Power BI Desktop (2026-10-05): first open failed ("'Forecast' measure cannot be created because a
  column with the same name already exists": DAX names are case-insensitive) -> 4 measure/column clashes renamed and a
  name-clash guard added. Then opened, refreshed and every page inspected via computer use. User feedback "charts
  misaligned, too much text" -> redesigned on a fixed grid (24 px margins, 16 px gutters), text reduced to one takeaway
  line per page; automated overlap check (0 overlaps). Bugs found by inspection and fixed: empty per-period chart
  (slicer conflict), cramped slicers, meaningless table totals, raw column names on axes, 0-based coverage axes.
  Final: 10 pages, 72 visuals, 43 measures, all render with data; saved in Power BI 10:42 (data cache stored).
  Old report folders moved to _to_delete/ (deletion not permitted in the user's folder).
- docs/memo.md, docs/interview_walkthrough.md, docs/source_dictionary.md, README.md rewritten, requirements.txt
  (lightgbm pinned 4.6.0; unused scipy/sklearn/streamlit removed), environment/ locks for both machines.
- User's laptop .venv has lightgbm 4.7.0 (vs 4.6.0 here): likely cause of the cross-platform forecast difference.
- scripts/ets_crosscheck_statsmodels.py written (validation origins only), NOT run (statsmodels only on user's laptop).

## Reproduction check (2026-10-05): PASS 26/26
- Clean copy without results/derived data/frozen choices; pipeline rerun from prepared data with the README commands.
- 29 of 60 backtest weeks recomputed from scratch: forecasts identical (max diff 0); remaining 31 reused (stopped
  early at the user's request to save ~15 min). All later steps rerun fresh: tuning, model choice, interval
  multipliers, all frozen choices (incl. those first made on the Windows laptop), validation and holdout metrics,
  SQL recomputation, company tables and review lists match exactly (results/reproduction_check.csv).
- Bug found and fixed: scripts/run_sql.py did not create results/dashboard/, so sql/03 failed on a fresh clone.

## NEXT (resume here)
- Optional: user runs scripts/ets_crosscheck_statsmodels.py on the laptop; record the result here and in docs/memo.md.
- User can delete _to_delete/ and wdp_*.tgz transfer files from the project folder.
- If the dashboard is regenerated with powerbi/build_pbip.py, close Power BI first (or use "Apply external changes").
