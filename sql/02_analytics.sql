-- Analytical tables built in DuckDB from saved forecast results (run after checkpoint 4).
-- Independent recomputation of WAPE / bias / RMSSE used to reconcile the Python results and the dashboard.

CREATE OR REPLACE TABLE meta_idx AS
SELECT row_number() OVER (ORDER BY id) - 1 AS idx, id, store_id, cat_id, dept_id, volume_group, pattern_group
FROM panel_metadata;

CREATE OR REPLACE TABLE backtest_forecasts AS
SELECT * FROM read_csv('results/backtest/origins/1*.csv.gz', header = true, auto_detect = true, union_by_name = true);

CREATE OR REPLACE TABLE holdout_forecasts AS
SELECT * FROM read_csv('results/holdout/holdout_forecasts.csv.gz', header = true, auto_detect = true);

CREATE OR REPLACE TABLE forecast_eval AS
SELECT 'validation' AS period, * FROM backtest_forecasts
WHERE origin IN (1745, 1773, 1801, 1829, 1857, 1885)
UNION ALL
SELECT 'holdout' AS period, * FROM holdout_forecasts WHERE origin = 1913;

-- Guard: validation rows must not extend into the holdout; holdout rows must cover d_1914..d_1941.
CREATE OR REPLACE TABLE eval_guards AS
SELECT period, count(*) AS n_rows, min(d) AS min_d, max(d) AS max_d,
       sum(CASE WHEN y IS NULL THEN 1 ELSE 0 END) AS missing_actuals,
       count(DISTINCT idx) AS n_series, count(DISTINCT origin) AS n_origins
FROM forecast_eval GROUP BY period;

CREATE OR REPLACE TABLE series_rmsse AS
SELECT period, model, origin, idx, sqrt(avg(power(forecast - y, 2)) / any_value(scale)) AS rmsse
FROM forecast_eval GROUP BY ALL;

CREATE OR REPLACE TABLE forecast_metrics_sql AS
WITH seg AS (
  SELECT f.*, m.store_id, m.cat_id, m.volume_group, m.pattern_group FROM forecast_eval f JOIN meta_idx m USING (idx)
), unioned AS (
  SELECT period, model, 'all' AS segment_type, 'all' AS segment, forecast, y, idx, origin FROM seg
  UNION ALL SELECT period, model, 'volume_group', volume_group, forecast, y, idx, origin FROM seg
  UNION ALL SELECT period, model, 'pattern_group', pattern_group, forecast, y, idx, origin FROM seg
  UNION ALL SELECT period, model, 'store_id', store_id, forecast, y, idx, origin FROM seg
  UNION ALL SELECT period, model, 'cat_id', cat_id, forecast, y, idx, origin FROM seg
), agg AS (
  SELECT period, model, segment_type, segment,
         sum(abs(forecast - y)) / nullif(sum(y), 0) AS wape,
         sum(forecast - y) / nullif(sum(y), 0) AS bias,
         sum(y) AS actual_units
  FROM unioned GROUP BY ALL
), rm AS (
  SELECT u.period, u.model, u.segment_type, u.segment, avg(r.rmsse) AS mean_rmsse
  FROM (SELECT DISTINCT period, model, segment_type, segment, idx, origin FROM unioned) u
  JOIN series_rmsse r USING (period, model, idx, origin)
  GROUP BY ALL
)
SELECT * FROM agg JOIN rm USING (period, model, segment_type, segment)
ORDER BY period, segment_type, segment, model;

CREATE OR REPLACE TABLE priority_weekly AS
SELECT 'validation' AS period, rule, origin, K, captured_ae_share, captured_ne_share, precision, recall
FROM read_csv('results/checkpoint4/validation_rule_weekly_selected.csv', header = true, auto_detect = true)
UNION ALL
SELECT 'holdout', rule, origin, K, captured_ae_share, captured_ne_share, precision, recall
FROM read_csv('results/holdout/holdout_rule_weekly.csv', header = true, auto_detect = true);

CREATE OR REPLACE TABLE priority_summary_sql AS
SELECT period, rule, K, count(*) AS weeks, avg(captured_ae_share) AS captured_ae_mean,
       stddev_samp(captured_ae_share) AS captured_ae_sd, avg(captured_ne_share) AS captured_ne_mean,
       avg(precision) AS precision, avg(recall) AS recall
FROM priority_weekly GROUP BY ALL ORDER BY period, K, captured_ae_mean DESC;

COPY eval_guards TO 'results/analytics/sql_eval_guards.csv' (HEADER, DELIMITER ',');
COPY forecast_metrics_sql TO 'results/analytics/sql_forecast_metrics.csv' (HEADER, DELIMITER ',');
COPY priority_summary_sql TO 'results/analytics/sql_priority_summary.csv' (HEADER, DELIMITER ',');
