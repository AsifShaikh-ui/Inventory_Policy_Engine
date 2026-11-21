# This file is made for checking the honest zero share which is find in the availability file

import pandas as pd
import config

def main() -> None:
    avail = pd.read_parquet(config.PROCESSED_DIR / "avalability.parquet")
    pieces = []

    for f in sorted((config.INTERIM_DIR / "sales_long").glob("*.parquet")):
        store = f.stem
        df = pd.read_parquet(f, columns=["item_id", "d", "units_sold"])
        df["item_id"] = df["item_id"].astype(str)
        df["d_num"] = df["d"].astype(str).str.slice(2).astype("int16")

        start = avail.loc[avail["store_id"] == store, ["item_id", "first_price_day"]]
        df = df.merge(start, on="item_id" , how="left")

        df["available"] = df["d_num"] >= df["first_price_day"]
        df["zero"] = df["units_sold"] == 0
        df["zero_avail"] = df["zero"] & df["available"]

        g = df.groupby("item_id").agg(
            total_days = ("d_num", "size"),
            avail_days = ("available", "sum"),
            zero_days_all = ("zero", "sum"),
            zero_days_avail = ("zero_avail", "sum"),
            units_sold = ("units_sold", "sum")
        ).reset_index()
        pieces.append(g)
        print(f"{store}: done")

    series = pd.concat(pieces, ignore_index=True)
    series["zero_share_avail"] = series["zero_days_avail"] / series["avail_days"]
    series.to_parquet(config.PROCESSED_DIR / "series_status.parquet", index=False)

    total = series["total_days"].sum()
    avail_cells = series["avail_days"].sum()
    zeros_all = series["zero_days_all"].sum()
    zeros_avail = series["zero_days_avail"].sum()
    unavailable = total - avail_cells

    print(f"All Cells: {total:,}")
    print(f"Zero Share, all days: {zeros_all / total:.2%}")
    print(f"Availbale Cells: {avail_cells:,}")
    print(f"Unavailable Cells: {unavailable:,}")
    print(f"Zero share , availbale days only: {zeros_avail / avail_cells:.2%}")
    print(f"Check, every unavailable cells is zero: {zeros_all - zeros_avail == unavailable}")
    print(series["zero_share_avail"].describe(percentiles = [0.1, 0.5, 0.9]))

if __name__ == "__main__":
    main()