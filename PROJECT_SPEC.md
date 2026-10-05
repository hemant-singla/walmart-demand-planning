# Walmart Demand Planning: Forecast Reliability and Review Priorities

Independent historical public-data study. Build forecasts and a weekly investigation list, not claimed Walmart savings. This compact specification replaces the longer planning documents for implementation.

## Inputs and decision

Real M5 data, original Kaggle / downloaded Zenodo mirror. data/source_manifest.json records source and checksums. data/audit_summary.json describes actual preparation. data/prepared_schema.json describes compact files. scripts/download_data.py and prepare_data.py reproduce acquisition/preparation.

Use data/prepared: sales_pilot.csv or daily_sales_pilot.csv.gz for 30 series, then sales_panel.csv or daily_sales.csv.gz for 200; panel_metadata.csv; calendar.csv; sell_prices_panel.csv (pilot version also supplied). Wide and long sales are alternative representations, never additional observations. Raw files need not be read during modeling.

Panel is fixed using only first 730 days, with 100 food/household series per store (CA_1 and TX_1), stratified by early sales volume and zero-sales share. Eligibility requires at least 100 observed early sales units and 100 nonzero days. This excludes very sparse/new products; disclose representativeness limits. Do not alter the panel based on test performance. Check audit dates instead of guessing coverage.

Question: which forecasts are dependable, and which five product-store series should a planner investigate each week? Five is our workload scenario. Evaluate capacities 1, 5 and 10. A priority list identifies error exposure; it does not prove that humans can correct it.

## Pipeline

DuckDB SQL for source preparation/joins and analytical tables. Python for seasonal-naive, ETS and one global LightGBM forecast model. One Streamlit dashboard. Create a reproducible repository with SQL, Python, README, locked successful environment, source dictionary, evaluation files and a two-page decision memo. Do not add a chatbot, cloud deployment, deep learning or multiple BI tools.

Use load_data.sql as a starter. Relative paths assume project-root working directory. It has not been executed in DuckDB in the supplied package. Preserve unique id/day and store/item/week keys; verify source totals and no duplicated sales after joins. Missing observed prices are not automatically imputed.

## Time and leakage rules

Produce 28 daily forecast horizons. Prefer direct-horizon LightGBM or safe recursive prediction; future observed sales cannot fill lags. Future prices are unknown: use the last available price for an operational forecast. A separate known-price scenario is optional and explicitly labeled. Future known calendar dates/events are allowed.

Selection cutoff d_730. Reserve final 28 observed days as an untouched holdout. Before it, use chronological training, calibration and validation, at least six non-overlapping 28-day origins for forecasting comparisons if available. Specify date windows before tuning. Freeze model/ranking choices before final test. Refit at each origin with only then-available history; no tuning on future outcomes. Clearly handle model failures and zero/undefined metrics.

Weekly priorities use only prior out-of-sample errors, historical bias and forecast uncertainty. Build that error history from earlier origins, not fitted residuals. Evaluate each weekly selection using first seven future days, so adjacent weeks' error targets do not overlap. Report 28-day forecast results separately. Retrospective outcomes must not influence prospective lists.

## Experiment and metrics

Forecast baselines: repeat last observed week; ETS (document fallback); global LightGBM. Use limited tuning. Report mean item-level RMSSE, aggregate WAPE, signed bias, volume/zero-share segments and runtime. Handle denominator zero explicitly. This panel metric is not official full-hierarchy leaderboard WRMSSE. Model segmentation only if validation supports it.

Priority baselines: highest prior-28-day unit sales; largest recent out-of-sample forecast error; repeated seeded random selection. Proposed rule: transparent combination of recent error, persistent bias and calibrated uncertainty. Set normalization/weights on validation only; compare each signal alone. Recommend the simpler baseline if it wins. Do not claim the score is reliable before testing.

Metrics: fraction of subsequent seven-day absolute unit forecast error captured in top K; precision/recall for a large normalized-error event whose threshold is fixed from earlier calibration; variation across origins and K=1/5/10. Evaluate unit exposure and normalized error separately to disclose volume dominance. Captured errors are not avoided errors. Report negative findings.

Provide an uncertainty range using past out-of-sample errors or quantile modeling; evaluate nominal coverage and interval width by segment. Calendar associations and price changes are not causal promotional effects.

## Dashboard and acceptance

Show source coverage, model comparisons, an as-of-date prioritized review table with evidence and suggested investigation, product forecasts/uncertainty, and a separate retrospective evaluation view. Flag explanations describe observed bias/change/uncertainty, not invented stockouts or supplier delays.

Check data keys/totals, timing cutoffs, sample independence, multi-step features, metric edge cases, baseline equivalence and dashboard-to-result reconciliation. Freeze final holdout until choices are recorded. Save actual executions and failure cases. Another person must reproduce the results. Do not promise a target improvement.

Memo: decision, actual data, tested alternatives, measured result, failure case, recommendation and missing data. No actual inventory, lead time, margin or human override history exists here. No stockout reduction, cash savings or forecast-value-added claims. Be explicit that sales may be censored demand and the anonymized panel is not Walmart-wide.

## Checkpoints

1. Verify supplied data audit and schema; save project environment and SQL tables.
2. Pilot baseline and temporal validation.
3. Final-panel forecast comparisons and interval checks.
4. Equal-budget priority experiment; final holdout once choices freeze.
5. Dashboard, memo, README and interview explanation.

After each, save PROGRESS.md and machine-readable results; do not require a new chat prompt to continue unless blocked. Completed source preparation is not completed model validation.

## Sources

- https://www.kaggle.com/competitions/m5-forecasting-accuracy/data
- https://zenodo.org/records/10203108
- https://arxiv.org/abs/2108.03588
- https://doi.org/10.1016/j.ijforecast.2008.11.013
- https://doi.org/10.1016/j.ijforecast.2024.07.006
