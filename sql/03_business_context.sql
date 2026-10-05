-- Business context for the dashboard, from the FULL M5 sales file (30,490 series, 10 stores, 3 states).
-- Reads data/raw/sales_train_evaluation.csv (kept local, never redistributed); outputs only aggregates.
-- Calendar/SNAP/event comparisons are descriptive associations, not causal effects.
-- Run: python scripts/run_sql.py sql/03_business_context.sql --scope panel  (after 01_load_audit.sql)

CREATE OR REPLACE TABLE m5_wide AS
SELECT * FROM read_csv('data/raw/sales_train_evaluation.csv', header = true, auto_detect = true);

CREATE OR REPLACE TABLE m5_long AS
SELECT id, item_id, dept_id, cat_id, store_id, state_id,
       CAST(replace(d, 'd_', '') AS INTEGER) AS d_num, CAST(units AS INTEGER) AS units
FROM (UNPIVOT m5_wide ON COLUMNS('^d_[0-9]+$') INTO NAME d VALUE units);

CREATE OR REPLACE TABLE cal AS
SELECT d_num, CAST(date AS DATE) AS date, weekday, wday, month, year, wm_yr_wk,
       event_name_1, event_type_1, snap_CA, snap_TX, snap_WI
FROM calendar WHERE d_num <= 1941;

-- Guard: full-file totals.
CREATE OR REPLACE TABLE ctx_guard AS
SELECT count(*) AS rows, count(DISTINCT id) AS series, count(DISTINCT store_id) AS stores,
       count(DISTINCT d_num) AS days, sum(units) AS total_units,
       sum(CASE WHEN units < 0 OR units IS NULL THEN 1 ELSE 0 END) AS bad_units
FROM m5_long;

-- First day each series ever sold (series-days before it are "not yet launched").
CREATE OR REPLACE TABLE first_sale AS
SELECT id, min(d_num) AS first_d FROM m5_long WHERE units > 0 GROUP BY id;

-- 1. Daily sales by store x category (company trend lines).
CREATE OR REPLACE TABLE ctx_daily_store_cat AS
SELECT c.date, l.d_num, l.state_id, l.store_id, l.cat_id, sum(l.units) AS units,
       sum(CASE WHEN l.units > 0 THEN 1 ELSE 0 END) AS items_selling
FROM m5_long l JOIN cal c USING (d_num) GROUP BY ALL;

-- 2. Store summary.
CREATE OR REPLACE TABLE ctx_store_summary AS
WITH y AS (
  SELECT l.store_id, c.year, sum(l.units) / count(DISTINCT l.d_num) AS avg_daily_units
  FROM m5_long l JOIN cal c USING (d_num) WHERE c.year IN (2012, 2015) GROUP BY ALL)
SELECT l.state_id, l.store_id, count(DISTINCT l.id) AS series, sum(l.units) AS total_units,
       sum(l.units) / sum(sum(l.units)) OVER () AS share_of_units,
       avg(CASE WHEN l.units = 0 THEN 1.0 ELSE 0.0 END) FILTER (WHERE l.d_num >= f.first_d) AS zero_share_after_launch,
       any_value(y12.avg_daily_units) AS avg_daily_units_2012, any_value(y15.avg_daily_units) AS avg_daily_units_2015,
       any_value(y15.avg_daily_units) / any_value(y12.avg_daily_units) - 1 AS growth_2012_to_2015
FROM m5_long l JOIN first_sale f USING (id)
LEFT JOIN y y12 ON y12.store_id = l.store_id AND y12.year = 2012
LEFT JOIN y y15 ON y15.store_id = l.store_id AND y15.year = 2015
GROUP BY l.state_id, l.store_id ORDER BY l.store_id;

-- 3. Department summary (what the company sells, how intermittent it is).
CREATE OR REPLACE TABLE ctx_dept_summary AS
SELECT l.cat_id, l.dept_id, count(DISTINCT l.id) AS series, count(DISTINCT l.item_id) AS items,
       sum(l.units) AS total_units, sum(l.units) / sum(sum(l.units)) OVER () AS share_of_units,
       avg(CASE WHEN l.units = 0 THEN 1.0 ELSE 0.0 END) FILTER (WHERE l.d_num >= f.first_d) AS zero_share_after_launch,
       avg(l.units) FILTER (WHERE l.d_num >= f.first_d) AS avg_units_per_series_day
FROM m5_long l JOIN first_sale f USING (id) GROUP BY ALL ORDER BY l.dept_id;

-- 4. Monthly average daily sales by state x category (seasonality / growth; partial months handled by daily average).
CREATE OR REPLACE TABLE ctx_monthly AS
SELECT c.year, c.month, make_date(c.year, c.month, 1) AS month_start, l.state_id, l.cat_id,
       sum(l.units) / count(DISTINCT l.d_num) AS avg_daily_units
FROM m5_long l JOIN cal c USING (d_num) GROUP BY ALL ORDER BY month_start;

-- 5. Weekday pattern: average daily units by weekday, indexed to the week average (=100).
CREATE OR REPLACE TABLE ctx_weekday AS
WITH d AS (SELECT c.weekday, c.wday, l.state_id, l.cat_id, l.d_num, sum(l.units) AS units
           FROM m5_long l JOIN cal c USING (d_num) GROUP BY ALL),
a AS (SELECT weekday, wday, state_id, cat_id, avg(units) AS avg_daily_units FROM d GROUP BY ALL)
SELECT *, 100 * avg_daily_units / avg(avg_daily_units) OVER (PARTITION BY state_id, cat_id) AS index_vs_week
FROM a ORDER BY state_id, cat_id, wday;

-- 6. SNAP days (state food-assistance payment days) vs other days, same state, 2012-2015 full years.
CREATE OR REPLACE TABLE ctx_snap AS
WITH d AS (
  SELECT l.state_id, l.cat_id, l.d_num,
         CASE l.state_id WHEN 'CA' THEN c.snap_CA WHEN 'TX' THEN c.snap_TX ELSE c.snap_WI END AS snap,
         sum(l.units) AS units
  FROM m5_long l JOIN cal c USING (d_num) WHERE c.year BETWEEN 2012 AND 2015 GROUP BY ALL)
SELECT state_id, cat_id,
       avg(units) FILTER (WHERE snap = 1) AS avg_daily_units_snap,
       avg(units) FILTER (WHERE snap = 0) AS avg_daily_units_non_snap,
       avg(units) FILTER (WHERE snap = 1) / avg(units) FILTER (WHERE snap = 0) - 1 AS snap_uplift_association,
       count(*) FILTER (WHERE snap = 1) AS snap_days
FROM d GROUP BY ALL ORDER BY state_id, cat_id;

-- 7. Events: company sales on each event day vs the average of the same weekday in the 4 weeks before and after.
CREATE OR REPLACE TABLE ctx_events AS
WITH t AS (SELECT d_num, sum(units) AS units FROM m5_long GROUP BY d_num),
e AS (SELECT c.d_num, c.date, c.year, c.event_name_1, c.event_type_1 FROM cal c WHERE c.event_name_1 IS NOT NULL),
ref AS (
  SELECT e.d_num, avg(t.units) AS ref_units
  FROM e JOIN t ON t.d_num IN (e.d_num - 28, e.d_num - 21, e.d_num - 14, e.d_num - 7,
                              e.d_num + 7, e.d_num + 14, e.d_num + 21, e.d_num + 28)
  GROUP BY e.d_num)
SELECT e.event_name_1 AS event, e.event_type_1 AS event_type, count(*) AS occurrences,
       avg(t.units) AS avg_units_on_event_day, avg(r.ref_units) AS avg_units_same_weekday_nearby,
       avg(t.units / r.ref_units) - 1 AS lift_vs_nearby_same_weekday
FROM e JOIN t USING (d_num) JOIN ref r USING (d_num)
GROUP BY ALL ORDER BY lift_vs_nearby_same_weekday;

-- 8. Sales concentration (Pareto): cumulative share of units by series rank.
CREATE OR REPLACE TABLE ctx_pareto AS
WITH s AS (SELECT id, cat_id, sum(units) AS units FROM m5_long GROUP BY ALL),
r AS (SELECT *, row_number() OVER (ORDER BY units DESC) AS rnk, count(*) OVER () AS n,
             sum(units) OVER (ORDER BY units DESC ROWS UNBOUNDED PRECEDING) / sum(units) OVER () AS cum_share FROM s)
SELECT rnk, round(100.0 * rnk / n, 2) AS pct_of_series, cum_share FROM r
WHERE rnk % 100 = 0 OR rnk = n OR rnk IN (1, 10, 50) ORDER BY rnk;

-- 9. How intermittent are products? Distribution of zero-sales share (after launch) by category.
CREATE OR REPLACE TABLE ctx_zero_share AS
WITH s AS (SELECT l.id, l.cat_id, avg(CASE WHEN l.units = 0 THEN 1.0 ELSE 0.0 END) AS zero_share
           FROM m5_long l JOIN first_sale f USING (id) WHERE l.d_num >= f.first_d GROUP BY ALL)
SELECT cat_id, floor(zero_share * 10) / 10 AS zero_share_bin, count(*) AS series
FROM s GROUP BY ALL ORDER BY cat_id, zero_share_bin;

-- 10. Our 200-series panel vs the company (representativeness).
CREATE OR REPLACE TABLE ctx_panel_vs_m5 AS
WITH base AS (
  SELECT l.*, (l.id IN (SELECT id FROM panel_metadata)) AS in_panel,
         (l.store_id IN ('CA_1', 'TX_1') AND l.cat_id IN ('FOODS', 'HOUSEHOLD')) AS in_universe
  FROM m5_long l JOIN first_sale f USING (id) WHERE l.d_num >= f.first_d),
g AS (
  SELECT 'All M5 (10 stores, 3 categories)' AS population, * FROM base
  UNION ALL SELECT 'CA_1 + TX_1, FOODS + HOUSEHOLD (sampling universe)', * FROM base WHERE in_universe
  UNION ALL SELECT 'Our 200-series panel', * FROM base WHERE in_panel)
SELECT population, count(DISTINCT id) AS series, sum(units) AS total_units,
       avg(units) AS avg_units_per_series_day,
       avg(CASE WHEN units = 0 THEN 1.0 ELSE 0.0 END) AS zero_share_after_launch,
       sum(units) FILTER (WHERE cat_id = 'FOODS') / sum(units) AS foods_share_of_units
FROM g GROUP BY population ORDER BY series DESC;

-- 11. Panel price behaviour (panel prices only): how often weekly shelf prices change.
CREATE OR REPLACE TABLE ctx_price_changes AS
WITH p AS (SELECT store_id, item_id, wm_yr_wk, sell_price,
                  lag(sell_price) OVER (PARTITION BY store_id, item_id ORDER BY wm_yr_wk) AS prev
           FROM prices)
SELECT store_id, count(*) AS item_weeks,
       avg(CASE WHEN prev IS NOT NULL AND sell_price <> prev THEN 1.0 ELSE 0.0 END) AS share_weeks_price_changed,
       avg(CASE WHEN prev IS NOT NULL AND sell_price < prev THEN 1.0 ELSE 0.0 END) AS share_weeks_price_cut,
       median(sell_price) AS median_price
FROM p GROUP BY store_id;

COPY ctx_guard TO 'results/dashboard/ctx_guard.csv' (HEADER, DELIMITER ',');
COPY ctx_daily_store_cat TO 'results/dashboard/ctx_daily_store_cat.csv' (HEADER, DELIMITER ',');
COPY ctx_store_summary TO 'results/dashboard/ctx_store_summary.csv' (HEADER, DELIMITER ',');
COPY ctx_dept_summary TO 'results/dashboard/ctx_dept_summary.csv' (HEADER, DELIMITER ',');
COPY ctx_monthly TO 'results/dashboard/ctx_monthly.csv' (HEADER, DELIMITER ',');
COPY ctx_weekday TO 'results/dashboard/ctx_weekday.csv' (HEADER, DELIMITER ',');
COPY ctx_snap TO 'results/dashboard/ctx_snap.csv' (HEADER, DELIMITER ',');
COPY ctx_events TO 'results/dashboard/ctx_events.csv' (HEADER, DELIMITER ',');
COPY ctx_pareto TO 'results/dashboard/ctx_pareto.csv' (HEADER, DELIMITER ',');
COPY ctx_zero_share TO 'results/dashboard/ctx_zero_share.csv' (HEADER, DELIMITER ',');
COPY ctx_panel_vs_m5 TO 'results/dashboard/ctx_panel_vs_m5.csv' (HEADER, DELIMITER ',');
COPY ctx_price_changes TO 'results/dashboard/ctx_price_changes.csv' (HEADER, DELIMITER ',');

DROP TABLE m5_wide;
