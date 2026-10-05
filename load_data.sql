-- Starter SQL; execute from the project root with DuckDB.
-- Not yet executed in DuckDB by the data-preparation handoff.
CREATE OR REPLACE TABLE daily_sales AS
SELECT * FROM read_csv_auto('data/prepared/daily_sales.csv.gz');
CREATE OR REPLACE TABLE calendar AS
SELECT * FROM read_csv_auto('data/prepared/calendar.csv');
CREATE OR REPLACE TABLE prices AS
SELECT * FROM read_csv_auto('data/prepared/sell_prices_panel.csv');
CREATE OR REPLACE TABLE panel_metadata AS
SELECT * FROM read_csv_auto('data/prepared/panel_metadata.csv');
CREATE OR REPLACE VIEW observed_history AS
SELECT s.*, c.date, c.wm_yr_wk, c.wday, c.month, c.year,
       c.event_name_1, c.event_type_1, c.event_name_2, c.event_type_2,
       c.snap_CA, c.snap_TX, c.snap_WI, p.sell_price
FROM daily_sales s
LEFT JOIN calendar c ON s.d = c.d
LEFT JOIN prices p
  ON s.store_id = p.store_id AND s.item_id = p.item_id
 AND c.wm_yr_wk = p.wm_yr_wk;
-- observed_history is retrospective: apply origin cutoffs before features.
-- Do not use this view's future prices as known forecast inputs.
