import pandas as pd
import config

def build_sales_long(sales : pd.DataFrame) -> None:
    # reshape wide sales to ling , one store at a time 
    out_dir = config.INTERIM_DIR / "sales_long"
    out_dir.mkdir(parents=True, exist_ok=True)

    day_cols = [c for c in sales.columns if c.startswith("d_")]

    for store_id , store_df in sales.groupby("store_id"):
        long_df = store_df.melt(
            id_vars=['item_id', 'store_id'],
            value_vars=day_cols,
            var_name="d",
            value_name="units_sold"
        )
        long_df["units_sold"] = long_df["units_sold"].astype("int16")
        long_df["item_id"] = long_df["item_id"].astype("category")
        long_df["store_id"] = long_df["store_id"].astype("category")
        long_df["d"] = long_df["d"].astype("category")

        long_df.to_parquet(out_dir / f"{store_id}.parquet", index=False)
        print(f"{store_id}: {len(long_df):,} rows saved")


def build_dimensions(sales : pd.DataFrame) -> None:
    # small lookup tables : items , store , calendar.

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    items = sales[config.ITEM_COLS].drop_duplicates()
    stores = sales[config.STORE_COLS].drop_duplicates()

    items.to_parquet(config.PROCESSED_DIR / "items.parquet", index=False)
    stores.to_parquet(config.PROCESSED_DIR / "stores.parquet", index=False)

    calendar = pd.read_csv(config.CALENDAR_FILE, parse_dates=["date"])
    event_cols = ["event_name_1", "event_type_1", "event_name_2", "event_type_2"]
    calendar[event_cols] = calendar[event_cols].fillna("none")
    calendar.to_parquet(config.PROCESSED_DIR / "calendar.parquet", index=False)

    print(f"items : {len(items):,} rows saved")


def build_prices() -> None:
    prices = pd.read_csv(config.PRICE_FILE)
    prices["sell_price"] = prices["sell_price"].astype("float32")
    prices.to_parquet(config.PROCESSED_DIR / "weekly_pricess.parquet", index=False)

    print(f"prices: {len(prices):,} rows saved")

if __name__ == "__main__":
    sales = pd.read_csv(config.SALES_FILE)
    build_sales_long(sales)
    build_dimensions(sales)
    build_prices()
