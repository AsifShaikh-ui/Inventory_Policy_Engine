# This file is made for checking the first price day and if stock is sold before the first price day

import pandas as pd
import config

def first_price_day_per_series() -> pd.DataFrame:
    # for each item and store : thye first day it had a price
    
    prices = pd.read_parquet(config.PROCESSED_DIR / "weekly_pricess.parquet")
    calendar = pd.read_parquet(config.PROCESSED_DIR / "calendar.parquet")

    calendar['d_num'] = calendar['d'].str.slice(2).astype(int)

    week_start = calendar.groupby("wm_yr_wk")["d_num"].min()

    first_price = (
        prices.groupby(['store_id','item_id'], as_index=False)["wm_yr_wk"].min().rename(columns = {
            "wm_yr_wk" : "first_price_week"
        })
    )

    first_price["first_price_day"] = first_price["first_price_week"].map(week_start)
    first_price["store_id"] = first_price["store_id"].astype(str)
    first_price["item_id"] = first_price["item_id"].astype(str)
    return first_price[["store_id", "item_id", "first_price_day"]]


def first_sale_day_per_series() -> pd.DataFrame:
    # for each item and store : the first day with units sold above Zero

    pieces = []
    for f in sorted((config.INTERIM_DIR / "sales_long").glob("*.parquet")):
        df = pd.read_parquet(f, columns=["item_id", "d", "units_sold"])
        sold = df[df["units_sold"]> 0].copy()
        sold["d_num"] = sold["d"].astype(str).str.slice(2).astype(int)

        first = (
            sold.groupby("item_id", observed=True)["d_num"]
            .min()
            .rename("first_sale_day")
            .reset_index()
        )

        first["item_id"] = first["item_id"].astype(str)
        first["store_id"] = f.stem
        pieces.append(first)
        print(f"{f.stem}: done")

    return pd.concat(pieces, ignore_index=True)


def main() -> None:
    first_price = first_price_day_per_series()
    first_sale = first_sale_day_per_series()

    result = first_price.merge(first_sale, on=["store_id", "item_id"], how="left")
    result["sold_before_price"] = result["first_sale_day"] < result["first_price_day"]

    result.to_parquet(config.PROCESSED_DIR / "avalability.parquet", index=False)

    n = len(result)
    never_sold = result["first_sale_day"].isna().sum()
    before = result["sold_before_price"].sum()
    late = (result["first_price_day"] > 1).sum()

    print(f"Series (item_store pairs): {n:,}")
    print(f"Series with price starting after day 1 : {late:,} ({late / n:.1%})")
    print(f"Series that never sold: {never_sold:,}")
    print(f"Series that sold before their first price: {before:,} ({before / n:.2%})")

if __name__ == "__main__":
    main()