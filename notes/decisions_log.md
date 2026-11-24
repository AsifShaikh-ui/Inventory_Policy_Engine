# Decisions Log: Inventory Policy Engine

Each entry records what was decided, why, and what was given up. Interviewers often ask "why did you choose X over Y?"; the answers live here.

---

## D1. Project choice: Inventory Policy Engine on M5 data
- **Decision:** Build an inventory policy project (reorder points, safety stock, service level vs cost) using the M5 Walmart dataset.
- **Why:** It ends in a decision (what to reorder and when), not just a forecast. M5 is real, large retail data with prices and a calendar.
- **Given up:** Standalone customer segmentation, churn, and dashboard projects, which are common and weak for portfolios.
- **Limitation accepted:** No stock levels, costs, or lead times in the data, so these are assumed (see `assumptions.md`).

## D2. Portfolio set
- **Decision:** Three projects: Inventory Policy Engine (this one), Promotion Effectiveness and Pricing Simulator, and Mandi Price Monitor.
- **Why:** Each proves a different skill: optimization, statistical inference, and automated data pipelines.
- **Given up:** An SME operations project, because permitted real business data was not available.

## D3. Files used from M5
- **Decision:** Use `calendar.csv`, `sales_train_evaluation.csv`, and `sell_prices.csv`. Drop `sales_train_validation.csv` and `sample_submission.csv`.
- **Why:** The validation file is the same data stopping 28 days earlier; the sample submission is only a Kaggle format file.

## D4. Environment: uv
- **Decision:** Manage the Python environment and dependencies with uv; commit `pyproject.toml` and `uv.lock`.
- **Why:** Reproducible installs from a lockfile, in one tool.
- **Rule:** Add a library only when a phase needs it.

## D5. Table design: fact and lookup tables
- **Decision:** One daily sales fact table (grain: units of one item sold at one store on one day; columns `item_id`, `store_id`, `d`, `units_sold`), plus lookup tables for items, stores, and the calendar. Prices stay weekly and are joined when needed.
- **Why:** A narrow big table saves space and speeds up queries; descriptions are stored once.
- **Given up:** Copying prices onto 59 million daily rows.

## D6. Reshaping approach: wide to long, one store at a time
- **Decision:** Reshape the wide sales file store by store (10 pieces of about 5.9 million rows) and save each as Parquet.
- **Why:** The full long table is about 59.2 million rows; reshaping all at once risks running out of memory. Stores match how a manager thinks.
- **Alternative:** Slices of about 1,000 items would use less memory; switch to them if a store slice proves too heavy.

## D7. Storage format: Parquet
- **Decision:** Save intermediate and processed data as Parquet, not CSV.
- **Why:** Smaller and faster to read, and it keeps column types.

## D8. Calendar events: null means "no event"
- **Decision:** Fill empty event fields with the label "none".
- **Why:** The nulls are not missing data; they mean no event that day.

## D9. Treat zero sales carefully
- **Finding:** 68.00% of item-store-days have zero sales; 64.1% of item-store series have no price in the first week of the data.
- **Decision:** Plan to separate "not yet available" zeros from real zero-demand days, and to use methods suited to intermittent demand.
- **Status:** Assumption A2 is confirmed: across all 30,490 series, none sold before its first price week and none never sold. So "available from the first price week" is a safe rule. Mid-history price gaps are still unchecked.

## D10. Validation after ingest
- **Decision:** After loading, check that the total long-format rows equal 59,181,090 (30,490 series x 1,941 days), that there are no nulls, and that no sales are negative.
- **Why:** The pipeline should fail loudly if data is lost or damaged.

## D11. Classify series by revenue (ABC) and by demand pattern
- **Decision:** Classify each item-store series by ABC (cumulative revenue, 80/15/5) and by demand pattern (smooth, erratic, intermittent, lumpy) using ADI 1.32 and CV2 0.49, on available days only.
- **Why:** Classic XYZ uses one variation measure and fails when 60% of days are zero. ADI and CV2 are made for intermittent demand.
- **Result:** 72.6% intermittent, 18.4% lumpy, 6.2% smooth, 2.8% erratic. Forecast and policy choices must handle intermittent demand.
- **Given up:** Margin-based ABC (no cost data), and item-level classes across stores.

## D12. Forecast method: 28-day moving average as the main forecast
- **Test:** rolling-origin comparison on a sample of 807 item-store series (stratified by ABC and demand class), 8 cut-off dates 28 days apart, 6,428 test rows. Each method forecast the next 7 days total (lead time assumption B1), using only available days before the cut-off. Scored by WAPE and bias on 7-day totals.
- **Overall WAPE:** zero 1.000 (sanity check), 28-day moving average 0.340, TSB 0.342, 90-day moving average 0.371, SBA 0.380. Bias within 2.4% for all non-zero methods.
- **By demand class (WAPE):** intermittent: TSB 0.417, MA28 0.425, MA90 0.464, SBA 0.492. Lumpy: TSB 0.441, MA28 0.447, MA90 0.491, SBA 0.545. Smooth: MA28 0.249, TSB 0.255, SBA 0.258, MA90 0.270. Erratic: MA28 0.356, TSB 0.361, MA90 0.390, SBA 0.391.
- **Decision:** use the 28-day moving average as the main forecast. TSB stays as a challenger for intermittent and lumpy series, where it is slightly ahead, but the gaps (0.002 to 0.008) are small and not tested for significance.
- **Why:** no method clearly beats the simple baseline. Croston/SBA, the method usually recommended for intermittent demand, did worst here.
- **Caveats:** smoothing parameters (0.1) were not tuned; the sample is 807 of 30,490 series; WAPE is dominated by high-volume series; WAPE of about 0.34 means the 7-day total is off by about a third of volume on average, which is exactly why safety stock is needed.

## D13. Safety stock from real forecast misses, by ABC x demand class
- **Method:** forecast = 28-day average x 7 days. At 8 past test dates per series, miss = actual 7-day demand minus forecast, divided by the series' normal weekly level (average daily sales over available history x 7). Safety stock ratio = the percentile of these miss ratios that matches the class service level (A 98%, B 95%, C 90%), per ABC x demand class. Safety stock = ratio x the series' own weekly level. Reorder point = forecast + safety stock.
- **Why percentiles of real misses:** demand is 60% zero days and bursty, so the textbook bell-curve formula does not fit. Groups under 500 test rows (B-erratic, C-erratic, C-smooth; 87 series) use the pooled ABC value.
- **Result:** 243,675 test rows. Ratios by class (A / B / C): smooth 0.775 / 0.645 / pooled; erratic 1.007 / pooled / pooled; intermittent 1.489 / 1.452 / 1.548; lumpy 1.582 / 1.248 / 1.267. Total 7-day forecast 307,941 units; total safety stock 350,515 units (114% of one week of demand).
- **Caveats:**
  - The in-sample coverage check (0.98 / 0.95 / 0.90) is nearly circular. It shows the code works, not that the policy works. The backtest is the real test.
  - Service level here is the share of 7-day windows covered, not fill rate.
  - C-class ratios are not smaller than A despite a lower service level, because very slow series have noisy misses relative to their small level.
  - The pooled fallback is dominated by intermittent rows, so the 87 pooled series (smooth and erratic) probably get buffers that are too large.
  - Very slow items can end up with reorder points below 1 unit; rounding rule not yet decided.
  - The ratio table uses the same 8 windows it is measured on; the backtest must fit it on earlier data only.

## D14. Backtest: our policy vs "N days of average sales"
- **Setup:** replay the last 224 days (days 1718 to 1941) for all 30,490 series. Safety stock ratios are fitted only on forecast misses that ended before the test period. Daily review, 7-day delivery, lost sales, reorder points rounded up to whole units, order up to reorder point plus one normal week (assumption B8). Costs: holding 20% a year on stock at 70% of price, $2 per order, lost margin at 30% of price (B3 to B6).
- **Results (all series, $2 per order):** fill rate / average stock value / total cost.
  - Baseline 7 days: 0.828 / 531,318 / 3,085,249
  - Baseline 14 days: 0.956 / 1,057,181 / 2,197,017
  - Baseline 21 days: 0.983 / 1,640,874 / 2,067,578
  - Baseline 30 days: 0.992 / 2,408,148 / 2,092,763
  - Baseline 45 days: 0.996 / 3,694,625 / 2,216,553
  - Ours, low service levels: 0.980 / 1,048,852 / 1,916,558
  - Ours, default service levels: 0.989 / 1,294,648 / 1,891,765
  - Ours, high service levels: 0.995 / 1,783,557 / 1,907,962
- **Reading:** at about equal stock (about 1.05M), ours-low fills 98.0% against 95.6% for the 14-day baseline. Ours-default beats the 21-day baseline on all three measures (fill 0.989 vs 0.983, stock 21% lower, total cost 8.5% lower). Against the 30-day baseline, ours-default holds 46% less stock for 0.3 points less fill rate and 9.6% lower total cost. Ours-high holds 52% less stock than the 45-day baseline for 0.1 point less fill rate.
- **Order cost sensitivity (lowest cost baseline vs lowest cost ours):** $0: 368,294 vs 261,429 (29% lower). $2: 2,067,578 vs 1,891,765 (8.5% lower). $10: 8,772,889 vs 8,380,390 (4.5% lower). The advantage shrinks as ordering gets expensive.
- **By class (default vs 30-day baseline):** stock 49% lower in A, 42% lower in B, 34% lower in C; fill rate 0.2, 0.4 and 0.8 points lower.
- **Caveats:**
  - These are hypothetical results under assumed costs, not measured savings.
  - Ordering cost is 85% or more of every policy's total cost at $2, because the order rule reorders after almost every sale of a slow item (about 27 orders per series in 224 days, close to equal across policies). The cost comparison is therefore weak at higher order costs; the stock and fill rate comparison is the stronger result.
  - Lost margin is higher under ours than under the 30-day baseline (102,524 vs 77,187); holding cost is lower (158,905 vs 295,575).
  - One 224-day window, one lead time, one order rule, no promotions.
  - The ABC and demand classes were computed on all history, a mild leak. Forecasts and buffer ratios use only past data.
- **Bug found and fixed:** the first run showed identical results for the three service-level sets because `build_safety_table` ignored the levels it was given. The rerun gives different results, as it should.