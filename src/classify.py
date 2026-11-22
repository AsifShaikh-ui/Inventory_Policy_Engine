# This file is made for grouping items so they get their own rules
#Because gives one rule for all 30,490 item-store pair waste efffort and cash

import numpy as np
import pandas as pd
import config

def store_stats(store: str, avail, prices, week_of_day) -> pd.DataFrame:
    # per-item stats for one store , availabe days only.

    df = pd.read_parquet(
        config.INTERIM_DIR / "sales_long" / f"{store}.parquet",
        columns=["item_id", "d", "units_sold"]
    )

    df["item_id"] = df["item_id"].astype(str)
    df["d_num"] = df["d"].astype(str).str.slice(2).astype("int16")
    df = df.drop(columns="d")

    start = avail.loc[avail["store_id"] == store, ["item_id", "first_price_day"]]
    df = df.merge(start, on="item_id", how="left")
    df = df[df["d_num"] >= df["first_price_day"]].copy()

    df["wm_yr_wk"] = df["d_num"].map(week_of_day)
    df = df.merge(prices, on=["item_id", "wm_yr_wk"], how="left")

    df["revenue"] = df["units_sold"] * df["sell_price"]
    df["sold"] = df["units_sold"] >0
    df["no_price"] = df["sell_price"].isna()

    base = df.groupby("item_id").agg(
        avail_days = ("d_num", "size"),
        sale_days = ("sold", "sum"),
        units_total = ("units_sold", "sum"),
        revenue = ("revenue", "sum"),
        missing_price_days = ("no_price", "sum")
    )

    sizes = (
        df[df["sold"]].groupby("item_id")["units_sold"].agg(mean_size = "mean", std_size = "std")
    )
    out = base.join(sizes).reset_index()
    out["std_size"] = out["std_size"].fillna(0)
    out["store_id"] = store
    return out


def main() -> None:
    avail = pd.read_parquet(config.PROCESSED_DIR / "avalability.parquet")
    calendar = pd.read_parquet(config.PROCESSED_DIR / "calendar.parquet")
    all_prices = pd.read_parquet(config.PROCESSED_DIR / "weekly_pricess.parquet")

    calendar["d_num"] = calendar["d"].str.slice(2).astype(int)
    week_of_day = calendar.set_index("d_num")["wm_yr_wk"]
    all_prices["item_id"] = all_prices["item_id"].astype(str)
    all_prices["store_id"] = all_prices["store_id"].astype(str)

    pieces = []
    for f in sorted((config.INTERIM_DIR / "sales_long").glob("*.parquet")):
        store = f.stem
        prices = all_prices.loc[
            all_prices["store_id"] == store, ["item_id", "wm_yr_wk", "sell_price"]
        ]
        pieces.append(store_stats(store, avail, prices, week_of_day))
        print(f"{store}: done")

    s = pd.concat(pieces, ignore_index=True)

    s["adi"] = s["avail_days"] / s["sale_days"]
    s["cv2"] = (s["std_size"] / s["mean_size"])**2
    frequent = s["adi"] < config.ADI_CUTOFF
    steady = s["cv2"] < config.CV2_CUTOFF
    s["demand_class"] = np.select(
        [frequent & steady, frequent & ~steady, ~frequent & steady],
        ["smooth", "erratic", "intermittent"],
        default="lumpy"
    )

    s = s.sort_values("revenue", ascending = False).reset_index(drop = True)
    s["cum_share"] = s["revenue"].cumsum() / s["revenue"].sum()
    s["abc"] = np.select(
        [s["cum_share"] <= config.ABC_A_SHARE, s["cum_share"] <= config.ABC_B_SHARE],
        ["A", "B"],
        default="C"
    )

    s.to_parquet(config.PROCESSED_DIR / "item_classes.parquet", index = False)

    print(f"Series Classified: {len(s):,}")
    print(f"Available days with no price row: {s["missing_price_days"].sum():,}")
    print("\nSeries per ABC class:")
    print(s["abc"].value_counts().sort_index())
    print("\nRevenue Share per ABC class:")
    print((s.groupby("abc")["revenue"].sum() / s["revenue"].sum()).round(4))
    print("\nSeries per demand class:")
    print(s["demand_class"].value_counts())
    print("\nABC X demand class (series count):")
    print(pd.crosstab(s["abc"], s["demand_class"]))

if __name__ == "__main__":
    main()