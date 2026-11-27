-- Check 0: calendar span (expected 1969 days)
SELECT COUNT(*) AS calendar_days, MIN("date") AS first_date, MAX("date") AS last_date
FROM calendar;

-- Check 1: total sales rows (expected 59181090)
SELECT COUNT(*) AS total_rows, COUNT(*) = 59181090 AS matches_expected
FROM sales;

-- Check 2: null keys and negative sales (both should be 0)
SELECT SUM(CASE WHEN item_id IS NULL OR store_id IS NULL OR d_num IS NULL THEN 1 ELSE 0 END) AS null_keys,
       SUM(CASE WHEN units_sold < 0 THEN 1 ELSE 0 END) AS negative_sales
FROM sales;

-- Check 3: one row per item and day in every store (expected 3049 items, 1941 days, TRUE)
SELECT store_id,
       COUNT(*) AS total_rows,
       COUNT(DISTINCT item_id) AS items,
       COUNT(DISTINCT d_num) AS days,
       COUNT(*) = COUNT(DISTINCT item_id || '|' || CAST(d_num AS VARCHAR)) AS one_row_per_item_day
FROM sales
GROUP BY store_id
ORDER BY store_id;

-- Check 4: series counts across tables (all four should be 30490)
SELECT (SELECT COUNT(*) FROM (SELECT DISTINCT store_id, item_id FROM sales)) AS sales_series,
       (SELECT COUNT(*) FROM availability) AS availability_rows,
       (SELECT COUNT(*) FROM item_classes) AS class_rows,
       (SELECT COUNT(*) FROM policy) AS policy_rows;

-- Check 5: days with a sale before the item's first price day (should be 0)
SELECT COUNT(*) AS sale_days_before_first_price
FROM sales s
JOIN availability a ON a.store_id = s.store_id AND a.item_id = s.item_id
WHERE s.d_num < a.first_price_day AND s.units_sold > 0;

-- Check 6: zero share on all days and on available days (expected 68.00 and 59.60)
SELECT ROUND(100.0 * AVG(CASE WHEN s.units_sold = 0 THEN 1 ELSE 0 END), 2) AS zero_share_all_days,
       ROUND(100.0 * SUM(CASE WHEN s.units_sold = 0 AND s.d_num >= a.first_price_day THEN 1 ELSE 0 END)
             / SUM(CASE WHEN s.d_num >= a.first_price_day THEN 1 ELSE 0 END), 2) AS zero_share_available_days
FROM sales s
JOIN availability a ON a.store_id = s.store_id AND a.item_id = s.item_id;