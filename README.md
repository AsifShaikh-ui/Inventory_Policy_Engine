# Inventory Policy Engine

A store manager has to decide, for every product, when to reorder and how much safety stock to keep. This project turns five years of real retail sales into a reorder point for 30,490 item-store series and tests it against the common rule "reorder at N days of average sales".

All costs and the 7-day delivery time are **assumptions**, because the data has no stock levels, costs or lead times. Backtest results are **hypothetical outcomes under those assumptions, not measured savings.**

## Headline result

On 30,490 item-store series replayed over the last 224 days of history, a safety stock policy sized from real forecast misses held 14% to 21% less stock than the best N-day-of-sales rule at equal or higher fill rate, and cost 8.5% to 10.6% less in total at $2 per order, under four different order rules. The advantage shrinks to 3.0% to 4.5% when each order costs $10. Details, caveats and the full numbers are in `reports/case_study.md`.

## The business problem

- **Who:** store and category managers who place replenishment orders.
- **Decision:** for each product, the reorder point (when to order) and the safety stock (how much buffer).
- **Success measures:** fill rate (share of demanded units sold), money held in stock, and total cost (holding + ordering + lost margin).

## Data

M5 Forecasting (Walmart), from Kaggle: https://www.kaggle.com/c/m5-forecasting-accuracy

- 3 files used: `calendar.csv`, `sales_train_evaluation.csv`, `sell_prices.csv`.
- 10 stores in 3 US states, 3,049 items, 1,941 days of daily unit sales, and weekly prices (6.8 million rows).
- The data is **not** stored in this repository. Download it from Kaggle (accepting the competition rules) and place the three files in `data/raw/`.

## How to run

Requires [uv](https://docs.astral.sh/uv/). From the project root:

```
uv sync
uv run python src/ingest.py          # raw CSV -> long-format Parquet, one file per store
uv run python src/validate.py        # row count, nulls, negatives
uv run python src/availability.py    # first price day per item-store, sold-before-price check
uv run python src/zero_share.py      # zero share on days the item was on the shelf
uv run python src/classify.py        # ABC by revenue, demand pattern per series
uv run python src/forecast.py        # optional: forecast method comparison on a sample
uv run python src/policy.py          # safety stock and reorder points
uv run python src/backtest.py        # replay the last 224 days under each policy and order rule
uv run python src/build_app_data.py  # small files for the app
uv run streamlit run app/streamlit_app.py
```

The full pipeline processes about 59 million rows. Each store is handled separately to keep memory use low.

## What the project does

1. **Reshapes** the sales file from 1,941 day columns to one row per item, store and day, and validates it (59,181,090 rows).
2. **Finds when each product reached the shelf** from its first price week, and confirms that no series sold before it had a price. 64.1% of series start after the first week of the data.
3. **Separates "not yet on sale" zeros from real zero-demand days.** The zero share is 68.00% over all days and 59.60% over days the item was available.
4. **Classifies each series** by revenue (A, B, C) and by demand pattern (smooth, erratic, intermittent, lumpy). 91% of series are intermittent or lumpy.
5. **Compares forecast methods** on a sample of 807 series over 7-day totals. A 28-day moving average did as well as the intermittent-demand methods.
6. **Sizes safety stock** from the observed forecast misses of each ABC and demand class, at service targets of 98%, 95% and 90% for A, B and C.
7. **Backtests** the policy against 14, 21, 30 and 45-day rules with a daily replay, a 7-day delivery, and lost sales, under four order rules and three order costs. Buffers are fitted only on data before the test period.
8. **Shows the result in a Streamlit app:** reorder point per item, and the service-versus-stock trade-off.

## Project structure

```
src/        pipeline, analysis, policy and backtest scripts
app/        Streamlit app
notes/      data understanding, assumptions, decisions log, code walkthrough
reports/    case study and figures
data/       raw, interim, processed (not committed)
```

## Limitations

- Costs (holding 20% a year, unit cost 70% of price, order cost $2, lost margin 30%) and the 7-day delivery time are assumptions. Every assumption is listed in `notes/assumptions.md`.
- Observed sales stand in for demand. Stockouts may hide true demand, and the data cannot show them.
- One 224-day test window, one delivery time, and no promotions. Each item is reviewed daily.
- ABC revenue classes use selling price, not margin, and were computed over the full history.

## Screenshots

![Item reorder point](reports/figures/app_item.png)
![Policy trade-off](reports/figures/app_tradeoff.png)