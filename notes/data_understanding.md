# Data Understanding: M5 Forecasting (Walmart)

Phase 2 notes for the Inventory Policy Engine.
Source: Kaggle, "M5 Forecasting - Accuracy". Files are stored in `data/raw/` and are not committed to Git.

Items marked **VERIFY** are filled from the M5 documentation and must be confirmed against the actual files before the case study uses them.

---

## 1. Files: which we use and why

| File | Use? | Reason |
|---|---|---|
| `calendar.csv` | Yes | Real dates, weekdays, events; links day codes to weeks |
| `sales_train_evaluation.csv` | Yes | Daily unit sales per item and store, d_1 to d_1941 |
| `sell_prices.csv` | Yes | Weekly price per item per store |
| `sales_train_validation.csv` | No | Same data as the evaluation file but stops at d_1913; using both would duplicate data |
| `sample_submission.csv` | No | Kaggle submission format only; irrelevant to a business project |

Note: the Kaggle goal (predict the next 28 days) is not our goal. We use the data to make inventory decisions.

## 2. Shapes (rows x columns)

| File | Shape |
|---|---|
| `calendar.csv` | 1969 x 14 |
| `sales_train_evaluation.csv` | 30490 x 1947 (6 identifier columns + 1941 day columns) |
| `sell_prices.csv` | 6,841,121 x 4 |

## 3. One row represents...

- **calendar:** one calendar day (d_1 to d_1969), with its date, week code, weekday, events, and SNAP flags.
- **sales_train_evaluation:** one item in one store, with its unit sales for every day laid out across 1941 columns (30,490 = 3049 items x 10 stores).
- **sell_prices:** the price of one item in one store for one week (identified by `store_id`, `item_id`, `wm_yr_wk`).

## 4. Columns

### calendar.csv

| Column | Meaning |
|---|---|
| `date` | Calendar date |
| `wm_yr_wk` | Week identifier; links to the price file |
| `weekday` | Day name |
| `wday` | Day number within the week; 1 = Saturday (the data starts on a Saturday). VERIFY |
| `month` | Month number |
| `year` | Year |
| `d` | Day code (d_1, d_2, ...). Matches the sales file's day column names |
| `event_name_1`, `event_type_1` | First event or holiday on that date |
| `event_name_2`, `event_type_2` | Second event on the same date |
| `snap_CA`, `snap_TX`, `snap_WI` | 1 if SNAP food-assistance purchases were allowed in that state that day, else 0 |

### sales_train_evaluation.csv

| Column | Meaning |
|---|---|
| `id` | Unique row identifier (item + store) |
| `item_id` | Product identifier |
| `dept_id` | Department of the product |
| `cat_id` | Category of the product |
| `store_id` | Store identifier |
| `state_id` | US state of the store |
| `d_1` ... `d_1941` | Units of that item sold at that store on that day (a count of units, not money) |

### sell_prices.csv

| Column | Meaning |
|---|---|
| `store_id` | Store identifier (same as in the sales file) |
| `item_id` | Product identifier (same as in the sales file) |
| `wm_yr_wk` | Week identifier (same as in the calendar) |
| `sell_price` | Price of the item at the store for that week |

## 5. Null values

- **calendar:** nulls only in the four event columns.
  - `event_name_1` and `event_type_1`: 1807 nulls each (so 162 days have a first event).
  - `event_name_2` and `event_type_2`: 1964 nulls each (so only 5 days have a second event).
  - A null here means "no event that day". It is not missing data. Plan: fill with an explicit label later.
- **sales_train_evaluation, sell_prices:** no nulls.
- **No nulls does not mean no gaps.** `sell_prices` has a row only for weeks in which the item was priced at that store. A missing item/store/week row most likely means the item was not on sale in that store that week (for example, not yet launched). Measured: 19,558 of 30,490 item-store series (64.1%) have no price row in the first week of the data (wm_yr_wk 11101). Confirmed: no series sold before its first price week (0 of 30,490), and every series has at least one sale.

## 6. Join chain

```
sales (reshaped to long: one row per item, store, day)
   |  key: d  (value like "d_1", matches calendar.d)
   v
calendar
   |  brings in wm_yr_wk for that day
   v
prices
      keys: store_id + item_id + wm_yr_wk
```

- **Step 1 (sales -> calendar):** key = `d`. The sales file stores days as column names, so it must first be reshaped from wide to long so that `d` becomes a column.
- **Step 2 (calendar -> prices):** the calendar supplies `wm_yr_wk`; prices are then matched on `store_id` + `item_id` + `wm_yr_wk`.
- **Why not join prices directly to the calendar:** one `wm_yr_wk` covers 7 calendar days and also thousands of price rows. Joining the two directly is many-to-many and multiplies rows. The price must be looked up through the sales rows, which supply the item and store.

## 7. Questions answered from the data

1. Number of stores: 10
2. Number of states: 3
3. Number of items: 3049 (check: 3049 items x 10 stores = 30,490 rows, which matches the sales file)
4. Number of departments: 7. Number of categories: 3
5. Days of history: 1941 days of sales (d_1 to d_1941). The calendar has 1969 days because it also covers the 28 days after the sales end (the Kaggle forecast period). Those 28 days have no sales data and are excluded from our analysis.
6. Share of zero-sales cells: **68.00%** (40,241,819 zeros out of 59,181,090 cells, measured across the 1941 day columns of `sales_train_evaluation.csv`). Two reasons a zero occurs:
   - **No demand:** nobody wanted the item that day. A true zero.
   - **Stockout or item not yet available:** demand may have existed but could not be served. These zeros hide lost sales.
   The data cannot tell the two apart. This is a key limitation: observed sales are not the same as true demand.
7. What this data lacks for inventory decisions:
   - Stock on hand and stockout records
   - Unit cost (so no margin or inventory value; only selling price)
   - Supplier lead times and order history
   - Ordering cost and holding cost
   - Shelf life or product perishability
   - Promotion and markdown detail
   - Returns, damages, and shrinkage

   Consequence: costs and lead times must be assumed and listed in `notes/assumptions.md`. Backtest results are hypothetical, not measured savings.
8. Why 1941 day columns are a problem: dates live in column names, so grouping by date, joining the calendar, or plotting a time series is awkward. Reshape from wide to long: 30,490 x 1941 gives about 59.2 million rows, so this must be done in chunks or in a database and stored efficiently.

## 8. Data quality observations

- **Demand is intermittent.** 68.00% of item-store-days have zero sales, so most days have no sale and sales arrive in occasional bursts.
- **Implications for the method (to be handled in Phase 5):**
  - Forecasting methods that assume a steady flow of demand fit this data poorly; intermittent-demand methods need to be considered.
  - Safety stock formulas that assume normally distributed demand may misbehave on zero-heavy demand, so the choice must be made deliberately and explained.
  - A forecast of "average daily sales" alone is not enough for an ordering decision, because the average hides how lumpy the demand is.
- **Zero share on available days only: 59.60%** (27,942,406 zeros out of 46,881,677 available item-store-days). Of the 59,181,090 cells, 12,299,413 (20.8%) are days before the item's first price day; every one of them is zero. Removing them lowers the zero share from 68.00% to 59.60%, a drop of 8.4 percentage points. Demand stays strongly intermittent.
- **The zero share differs a lot between series** (30,490 item-store series, share of available days with zero sales): minimum 0.2%, 10th percentile 25.9%, median 63.4%, 90th percentile 88.5%, maximum 99.1%. The average (about 60%) hides this spread, so one policy for all items is not appropriate; items need to be grouped by demand pattern.
- **Many items start late.** Items without a price row in the first week of the data:
  - 19,558 of 30,490 item-store series (64.1%)
  - 2,718 of 3,049 items (89.1%) in at least one store
  - 1,592 of 3,049 items (52.2%) in all 10 stores, meaning they appear chain-wide only after the first week
  - So about 1,126 items (2,718 - 1,592) start at different times in different stores.
- **Implication:** zeros before an item's first price week are not demand zeros; the item was most likely not on sale. These "not yet available" zeros must be separated from real zero-demand days before forecasting, or the 68% figure and any demand model will be distorted. Confirmed by `availability.py`: no series sold before its first price week.
- **Price gaps after launch: none.** Across all available days of all 30,490 series, 0 days have no price row (checked in `classify.py`).

## 9. Item classification (ABC by revenue, demand pattern)

Computed on available days only, per item-store series, saved in `data/processed/item_classes.parquet`.

- ABC by revenue (units x weekly selling price): A = first 80% of revenue, B = next 15%, C = last 5%. The 80/15/5 split is by construction. Series counts: A 11,221 (36.8%), B 9,426 (30.9%), C 9,843 (32.3%). Revenue is not spread in the classic "20% of items, 80% of revenue" way; A takes over a third of series.
- Demand pattern from the average gap between sales (ADI, cut-off 1.32) and the squared variation of sale size (CV2, cut-off 0.49), the standard cut-offs from the intermittent-demand literature:
  - intermittent 22,143 (72.6%)
  - lumpy 5,612 (18.4%)
  - smooth 1,880 (6.2%)
  - erratic 855 (2.8%)
- ABC x demand class (series count):

| ABC | erratic | intermittent | lumpy | smooth |
|---|---|---|---|---|
| A | 788 | 6,475 | 2,210 | 1,748 |
| B | 61 | 7,304 | 1,949 | 112 |
| C | 6 | 8,364 | 1,453 | 20 |

- Finding: about 91% of series are intermittent or lumpy, including most A series (6,475 + 2,210 of 11,221). Methods built for steady demand fit only about 6% of series.
- Limitations: ABC uses revenue, not margin (no cost data). Classes are per item-store, not per item across the chain.