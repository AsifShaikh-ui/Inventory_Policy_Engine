import pandas as pd
import config

RECENT_DAYS = 120
SUM_COLS = ["demand", "sold", "inv_units", "inv_value", "orders", "lost_margin"]


def build_recent_sales() -> None:
    calendar = pd.read_parquet(config.PROCESSED_DIR / "calendar.parquet")
    calendar["d_num"] = calendar["d"].str.slice(2).astype(int)
    date_of_day = calendar.set_index("d_num")["date"]

    first_day = config.N_DAYS - RECENT_DAYS + 1
    parts = []
    for f in sorted((config.INTERIM_DIR / "sales_long").glob("*.parquet")):
        df = pd.read_parquet(f, columns=["item_id", "d", "units_sold"])
        d = df["d"].astype("category")
        d_values = d.cat.categories.astype(str).str.slice(2).astype(int).to_numpy()
        df["d_num"] = d_values[d.cat.codes.to_numpy()]
        df = df[df["d_num"] >= first_day].copy()
        df["item_id"] = df["item_id"].astype(str)
        df["store_id"] = f.stem
        parts.append(df[["store_id", "item_id", "d_num", "units_sold"]])
        print(f"{f.stem}: done")

    recent = pd.concat(parts, ignore_index=True)
    recent["date"] = recent["d_num"].map(date_of_day)
    recent.to_parquet(config.PROCESSED_DIR / "app_recent_sales.parquet", index=False)
    print(f"recent sales: {len(recent):,} rows")


def build_tradeoff() -> None:
    res = pd.read_parquet(config.PROCESSED_DIR / "backtest_rules.parquet")
    out = res.groupby(["rule", "scenario", "abc"], as_index=False)[SUM_COLS].sum()
    out.to_parquet(config.PROCESSED_DIR / "app_tradeoff.parquet", index=False)
    print(f"trade-off table: {len(out)} rows")


if __name__ == "__main__":
    build_recent_sales()
    build_tradeoff()