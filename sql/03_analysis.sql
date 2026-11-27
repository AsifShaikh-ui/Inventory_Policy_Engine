-- Build the monthly summary once (sales joined to calendar and prices, then aggregated)
CREATE OR REPLACE TABLE monthly AS
SELECT store_id, item_id,
       CAST(EXTRACT(year FROM sale_date) AS INTEGER) AS yr,
       CAST(EXTRACT(month FROM sale_date) AS INTEGER) AS mth,
       SUM(units_sold) AS units,
       SUM(revenue) AS revenue
FROM sales_priced
GROUP BY 1, 2, 3, 4;

-- Q1: How is revenue split between categories within each state?
SELECT st.state_id, i.cat_id,
       ROUND(SUM(m.revenue)) AS revenue,
       ROUND(100.0 * SUM(m.revenue) / SUM(SUM(m.revenue)) OVER (PARTITION BY st.state_id), 1) AS pct_of_state
FROM monthly m
JOIN items i ON i.item_id = m.item_id
JOIN stores st ON st.store_id = m.store_id
GROUP BY st.state_id, i.cat_id
ORDER BY st.state_id, revenue DESC;

-- Q2: ABC classes from a running revenue share (window function)
WITH s AS (
    SELECT store_id, item_id, SUM(revenue) AS revenue
    FROM monthly
    GROUP BY 1, 2
), r AS (
    SELECT *, SUM(revenue) OVER (ORDER BY revenue DESC) / SUM(revenue) OVER () AS cum_share
    FROM s
)
SELECT CASE WHEN cum_share <= 0.80 THEN 'A' WHEN cum_share <= 0.95 THEN 'B' ELSE 'C' END AS abc,
       COUNT(*) AS series,
       ROUND(SUM(revenue)) AS revenue,
       ROUND(100.0 * SUM(revenue) / (SELECT SUM(revenue) FROM s), 1) AS pct_of_revenue
FROM r
GROUP BY 1
ORDER BY 1;

-- Q3: Which 3 items earn the most in each store? (RANK per store)
WITH s AS (
    SELECT store_id, item_id, SUM(revenue) AS revenue
    FROM monthly
    GROUP BY 1, 2
), ranked AS (
    SELECT *, RANK() OVER (PARTITION BY store_id ORDER BY revenue DESC) AS rnk
    FROM s
)
SELECT r.store_id, r.rnk, r.item_id, i.cat_id, ROUND(r.revenue) AS revenue
FROM ranked r
JOIN items i ON i.item_id = r.item_id
WHERE r.rnk <= 3
ORDER BY r.store_id, r.rnk;

-- Q4: How does revenue per day move month to month and year on year? (LAG)
WITH m AS (
    SELECT yr, mth, SUM(revenue) AS revenue
    FROM monthly
    GROUP BY 1, 2
), d AS (
    SELECT "year" AS yr, "month" AS mth, COUNT(*) AS days
    FROM calendar
    WHERE d_num <= 1941
    GROUP BY 1, 2
), x AS (
    SELECT m.yr, m.mth, d.days, m.revenue / d.days AS rev_per_day
    FROM m
    JOIN d ON d.yr = m.yr AND d.mth = m.mth
)
SELECT yr, mth, days,
       ROUND(rev_per_day) AS revenue_per_day,
       ROUND(100.0 * (rev_per_day / LAG(rev_per_day) OVER (ORDER BY yr, mth) - 1), 1) AS pct_vs_prev_month,
       ROUND(100.0 * (rev_per_day / LAG(rev_per_day, 12) OVER (ORDER BY yr, mth) - 1), 1) AS pct_vs_year_ago
FROM x
ORDER BY yr, mth;

-- Q5: How often is a product on sale but not bought, by department? (zero share on available days)
SELECT COALESCE(i.dept_id, 'ALL') AS dept_id,
       COUNT(*) AS series,
       ROUND(100.0 * (1 - SUM(c.sale_days) * 1.0 / SUM(c.avail_days)), 1) AS zero_share_available_pct
FROM item_classes c
JOIN items i ON i.item_id = c.item_id
GROUP BY ROLLUP(i.dept_id)
ORDER BY i.dept_id NULLS LAST;

-- Q6: How many series start late, by category?
SELECT i.cat_id,
       COUNT(*) AS series,
       SUM(CASE WHEN a.first_price_day > 1 THEN 1 ELSE 0 END) AS late_start,
       ROUND(100.0 * AVG(CASE WHEN a.first_price_day > 1 THEN 1 ELSE 0 END), 1) AS pct_late
FROM availability a
JOIN items i ON i.item_id = a.item_id
GROUP BY i.cat_id
ORDER BY pct_late DESC;

-- Q7: Where does the revenue sit, by ABC class and demand pattern?
SELECT abc, demand_class,
       COUNT(*) AS series,
       ROUND(SUM(revenue)) AS revenue,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 1) AS pct_of_all_revenue
FROM item_classes
GROUP BY abc, demand_class
ORDER BY abc, demand_class;

-- Q8: Which policy is cheapest under each order rule? ($2 per order, rank within rule)
WITH t AS (
    SELECT rule, scenario,
           SUM(sold) / SUM(demand) AS fill_rate,
           SUM(inv_value) / 224 AS stock_value,
           SUM(inv_value) * 0.20 / 365 + SUM(orders) * 2.0 + SUM(lost_margin) AS total_cost
    FROM backtest_summary
    GROUP BY rule, scenario
), b AS (
    SELECT rule, MIN(total_cost) AS best_baseline_cost
    FROM t
    WHERE scenario LIKE 'base%'
    GROUP BY rule
)
SELECT t.rule, t.scenario,
       ROUND(t.fill_rate, 3) AS fill_rate,
       ROUND(t.stock_value) AS stock_value,
       ROUND(t.total_cost) AS total_cost,
       ROUND(100.0 * (1 - t.total_cost / b.best_baseline_cost), 1) AS pct_below_best_baseline,
       RANK() OVER (PARTITION BY t.rule ORDER BY t.total_cost) AS cost_rank
FROM t
JOIN b ON b.rule = t.rule
ORDER BY t.rule, cost_rank;

-- Q9: How big are the reorder points, and how many are tiny? (by ABC class)
SELECT abc,
       COUNT(*) AS series,
       ROUND(AVG(reorder_point), 1) AS avg_reorder_point,
       ROUND(100.0 * AVG(CASE WHEN reorder_point < 1 THEN 1 ELSE 0 END), 1) AS pct_below_1_unit,
       ROUND(100.0 * AVG(CASE WHEN reorder_point < 2 THEN 1 ELSE 0 END), 1) AS pct_below_2_units,
       ROUND(SUM(safety_stock)) AS total_safety_stock,
       ROUND(SUM(forecast_7d)) AS total_forecast_7d
FROM policy
GROUP BY abc
ORDER BY abc;

-- Q10: How many series are on sale at the end of each month? (assortment growth)
WITH m AS (
    SELECT "year" AS yr, "month" AS mth, MAX(d_num) AS last_day
    FROM calendar
    WHERE d_num <= 1941
    GROUP BY 1, 2
)
SELECT m.yr, m.mth, COUNT(*) AS series_on_sale
FROM m
JOIN availability a ON a.first_price_day <= m.last_day
GROUP BY m.yr, m.mth
ORDER BY m.yr, m.mth;