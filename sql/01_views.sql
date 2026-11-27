-- Views over the Parquet files. The runner executes this file before every query file.

CREATE OR REPLACE VIEW sales AS
SELECT CAST(item_id AS VARCHAR) AS item_id,
       CAST(store_id AS VARCHAR) AS store_id,
       CAST(SUBSTR(CAST(d AS VARCHAR), 3) AS INTEGER) AS d_num,
       units_sold
FROM read_parquet('{INTERIM}/sales_long/*.parquet');

CREATE OR REPLACE VIEW items AS
SELECT * FROM read_parquet('{PROCESSED}/items.parquet');

CREATE OR REPLACE VIEW stores AS
SELECT * FROM read_parquet('{PROCESSED}/stores.parquet');

CREATE OR REPLACE VIEW calendar AS
SELECT *, CAST(SUBSTR(d, 3) AS INTEGER) AS d_num
FROM read_parquet('{PROCESSED}/calendar.parquet');

CREATE OR REPLACE VIEW prices AS
SELECT * FROM read_parquet('{PROCESSED}/weekly_pricess.parquet');

CREATE OR REPLACE VIEW availability AS
SELECT * FROM read_parquet('{PROCESSED}/avalability.parquet');

CREATE OR REPLACE VIEW item_classes AS
SELECT * FROM read_parquet('{PROCESSED}/item_classes.parquet');

CREATE OR REPLACE VIEW policy AS
SELECT * FROM read_parquet('{PROCESSED}/policy_params.parquet');

CREATE OR REPLACE VIEW backtest_summary AS
SELECT * FROM read_parquet('{PROCESSED}/app_tradeoff.parquet');

-- The join chain from Phase 2: sales -> calendar (by day) -> prices (by store, item, week)
CREATE OR REPLACE VIEW sales_priced AS
SELECT s.item_id, s.store_id, s.d_num, c."date" AS sale_date, c.wm_yr_wk,
       s.units_sold, p.sell_price,
       s.units_sold * p.sell_price AS revenue
FROM sales s
JOIN calendar c ON c.d_num = s.d_num
LEFT JOIN prices p
       ON p.store_id = s.store_id
      AND p.item_id = s.item_id
      AND p.wm_yr_wk = c.wm_yr_wk;