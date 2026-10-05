-- Checkpoint 1: load prepared files, verify keys/totals/joins, build model input.
-- Run through scripts/run_sql.py, which substitutes {{SFX}} with "" (200-series panel)
-- or "_pilot" (30-series pilot) and {{PSFX}} with "_panel" or "_pilot" for prices.
-- Paths are relative to the project root.

CREATE OR REPLACE TABLE daily_sales{{SFX}} AS
SELECT id, item_id, dept_id, cat_id, store_id, state_id, d,
       CAST(replace(d, 'd_', '') AS INTEGER) AS d_num,
       CAST(units AS INTEGER) AS units
FROM read_csv('data/prepared/daily_sales{{SFX}}.csv.gz', header = true, auto_detect = true);

CREATE OR REPLACE TABLE calendar AS
SELECT *, CAST(replace(d, 'd_', '') AS INTEGER) AS d_num
FROM read_csv('data/prepared/calendar.csv', header = true, auto_detect = true);

CREATE OR REPLACE TABLE prices{{SFX}} AS
SELECT store_id, item_id, CAST(wm_yr_wk AS INTEGER) AS wm_yr_wk, CAST(sell_price AS DOUBLE) AS sell_price
FROM read_csv('data/prepared/sell_prices{{PSFX}}.csv', header = true, auto_detect = true);

CREATE OR REPLACE TABLE panel_metadata AS
SELECT * FROM read_csv('data/prepared/panel_metadata.csv', header = true, auto_detect = true);

-- Wide file, used only to reconcile against the long file (alternative representation, not extra data).
CREATE OR REPLACE TABLE sales_wide{{SFX}} AS
SELECT * FROM read_csv('data/prepared/sales{{WSFX}}.csv', header = true, auto_detect = true);

CREATE OR REPLACE TABLE wide_long{{SFX}} AS
SELECT id, CAST(replace(d, 'd_', '') AS INTEGER) AS d_num, CAST(units AS INTEGER) AS units
FROM (UNPIVOT sales_wide{{SFX}} ON COLUMNS('^d_[0-9]+$') INTO NAME d VALUE units);

-- Retrospective observed history. Same-week prices here are NOT forecast inputs;
-- Python lags price to the last completed week before each origin.
CREATE OR REPLACE TABLE observed_history{{SFX}} AS
SELECT s.id, s.item_id, s.dept_id, s.cat_id, s.store_id, s.state_id, s.d_num, s.units,
       c.date, c.wm_yr_wk, c.wday, c.month, c.year,
       c.event_name_1, c.event_type_1, c.event_name_2, c.event_type_2,
       CASE s.state_id WHEN 'CA' THEN c.snap_CA WHEN 'TX' THEN c.snap_TX ELSE c.snap_WI END AS snap,
       p.sell_price
FROM daily_sales{{SFX}} s
LEFT JOIN calendar c ON s.d_num = c.d_num
LEFT JOIN prices{{SFX}} p
  ON s.store_id = p.store_id AND s.item_id = p.item_id AND c.wm_yr_wk = p.wm_yr_wk;

CREATE OR REPLACE TABLE audit_checks{{SFX}} AS
WITH
a AS (SELECT count(*) AS n_rows, count(DISTINCT id) AS n_ids, count(DISTINCT d_num) AS n_days,
             min(d_num) AS min_d, max(d_num) AS max_d, sum(units) AS total_units,
             sum(CASE WHEN units IS NULL THEN 1 ELSE 0 END) AS null_units,
             sum(CASE WHEN units < 0 THEN 1 ELSE 0 END) AS neg_units
      FROM daily_sales{{SFX}}),
dup AS (SELECT count(*) AS dup_id_day FROM (SELECT id, d_num FROM daily_sales{{SFX}} GROUP BY 1, 2 HAVING count(*) > 1)),
pdup AS (SELECT count(*) AS dup_price_key FROM (SELECT store_id, item_id, wm_yr_wk FROM prices{{SFX}} GROUP BY 1, 2, 3 HAVING count(*) > 1)),
cdup AS (SELECT count(*) - count(DISTINCT d_num) AS dup_calendar_day FROM calendar),
w AS (SELECT count(*) AS wide_long_rows, sum(units) AS wide_total_units FROM wide_long{{SFX}}),
wm AS (SELECT count(*) AS wide_long_mismatch FROM wide_long{{SFX}} w
       FULL OUTER JOIN daily_sales{{SFX}} s ON w.id = s.id AND w.d_num = s.d_num
       WHERE w.units IS DISTINCT FROM s.units),
j AS (SELECT count(*) AS joined_rows, sum(units) AS joined_units,
             sum(CASE WHEN date IS NULL THEN 1 ELSE 0 END) AS missing_calendar,
             sum(CASE WHEN sell_price IS NULL THEN 1 ELSE 0 END) AS missing_price_days,
             sum(CASE WHEN sell_price IS NULL AND units > 0 THEN 1 ELSE 0 END) AS positive_sales_missing_price
      FROM observed_history{{SFX}}),
m AS (SELECT count(*) AS ids_not_in_metadata FROM (SELECT DISTINCT id FROM daily_sales{{SFX}}) s
      ANTI JOIN panel_metadata p ON s.id = p.id),
sel AS (SELECT count(*) AS selection_units_mismatch FROM panel_metadata p
        JOIN (SELECT id, sum(units) AS u, sum(CASE WHEN units > 0 THEN 1 ELSE 0 END) AS nz
              FROM daily_sales{{SFX}} WHERE d_num <= 730 GROUP BY id) s ON p.id = s.id
        WHERE p.selection_units <> s.u OR p.selection_nonzero_days <> s.nz)
SELECT * FROM a, dup, pdup, cdup, w, wm, j, m, sel;

-- Compact model input: one row per id/day (keys preserved), no imputation of missing prices.
CREATE OR REPLACE TABLE model_input{{SFX}} AS
SELECT id, store_id, cat_id, dept_id, state_id, d_num, units, wm_yr_wk, wday, month,
       event_type_1, event_type_2, snap, sell_price
FROM observed_history{{SFX}}
ORDER BY id, d_num;

COPY audit_checks{{SFX}} TO 'results/checkpoint1/sql_audit{{SFX}}.csv' (HEADER, DELIMITER ',');
COPY model_input{{SFX}} TO 'data/derived/model_input{{SFX}}.csv.gz' (HEADER, DELIMITER ',', COMPRESSION gzip);
