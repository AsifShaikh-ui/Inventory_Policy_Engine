import numpy as np
import pandas as pd
import config


def load_store_matrix(store: str):
    """One store: item names and a (items x days) array of units sold."""
    df = pd.read_parquet(
        config.INTERIM_DIR / "sales_long" / f"{store}.parquet",
        columns=["item_id", "d", "units_sold"],
    )
    codes, uniques = pd.factorize(df["item_id"].astype(str))
    d = df["d"].astype("category")
    d_values = d.cat.categories.astype(str).str.slice(2).astype(int).to_numpy()
    d_num = d_values[d.cat.codes.to_numpy()]

    y = np.zeros((len(uniques), config.N_DAYS), dtype=np.float32)
    y[codes, d_num - 1] = df["units_sold"].to_numpy()
    return np.asarray(uniques, dtype=str), y


def forecasts_at(csum, start, d):
    """For every item at day d: history length, 7-day forecast, normal weekly level."""
    rows = np.arange(csum.shape[0])
    lead = config.LEAD_TIME_DAYS
    n_hist = d - start + 1                      # available days up to d
    safe = np.maximum(n_hist, 1)
    win = np.minimum(config.MA_WINDOW, safe)    # never look before the item existed
    forecast = lead * (csum[:, d] - csum[rows, d - win]) / win
    level = lead * (csum[:, d] - csum[rows, start - 1]) / safe
    return n_hist, forecast, level


def build_safety_table(ev: pd.DataFrame) -> pd.DataFrame:
    """Safety stock as a share of weekly level, per ABC x demand class."""
    rows = []
    for abc, q in config.SERVICE_LEVELS.items():
        pooled_ss = max(ev.loc[ev["abc"] == abc, "miss_ratio"].quantile(q), 0.0)
        for dc in sorted(ev["demand_class"].unique()):
            g = ev.loc[(ev["abc"] == abc) & (ev["demand_class"] == dc), "miss_ratio"]
            if len(g) >= config.MIN_GROUP_ROWS:
                ss, source = max(g.quantile(q), 0.0), "group"
            else:
                ss, source = pooled_ss, "pooled"
            rows.append({
                "abc": abc, "demand_class": dc, "test_rows": len(g),
                "service_level": q, "ss_ratio": ss, "source": source,
            })
    return pd.DataFrame(rows)


def main() -> None:
    cls = pd.read_parquet(
        config.PROCESSED_DIR / "item_classes.parquet",
        columns=["store_id", "item_id", "abc", "demand_class"],
    )
    avail = pd.read_parquet(
        config.PROCESSED_DIR / "avalability.parquet",
        columns=["store_id", "item_id", "first_price_day"],
    )
    lead = config.LEAD_TIME_DAYS
    origins = [
        config.N_DAYS - lead - config.ORIGIN_STEP * k
        for k in range(config.N_ORIGINS)
    ]

    test_parts, now_parts = [], []
    for store in sorted(avail["store_id"].unique()):
        items, y = load_store_matrix(store)
        a = avail[avail["store_id"] == store].set_index("item_id")
        start = a.loc[items, "first_price_day"].to_numpy().astype(int)
        csum = np.concatenate(
            [np.zeros((len(items), 1)), np.cumsum(y, axis=1, dtype=np.float64)],
            axis=1,
        )

        # Past test dates: forecast vs what really happened
        for d in origins:
            n_hist, f, level = forecasts_at(csum, start, d)
            actual = csum[:, d + lead] - csum[:, d]
            ok = n_hist >= config.MIN_HISTORY
            test_parts.append(pd.DataFrame({
                "store_id": store, "item_id": items[ok], "origin": d,
                "forecast": f[ok], "level": level[ok], "actual": actual[ok],
            }))

        # Today: forecast for the next 7 days beyond the data
        _, f, level = forecasts_at(csum, start, config.N_DAYS)
        now_parts.append(pd.DataFrame({
            "store_id": store, "item_id": items,
            "forecast_7d": f, "level_7d": level,
        }))
        print(f"{store}: done")

    # Misses as a share of the series' normal weekly demand
    ev = pd.concat(test_parts, ignore_index=True)
    n_all = len(ev)
    ev = ev[ev["level"] > 0].copy()
    ev["miss_ratio"] = (ev["actual"] - ev["forecast"]) / ev["level"]
    ev = ev.merge(cls, on=["store_id", "item_id"], how="left")

    table = build_safety_table(ev)
    table.to_parquet(config.PROCESSED_DIR / "safety_stock_table.parquet", index=False)

    # Reorder point per series
    now = pd.concat(now_parts, ignore_index=True).merge(
        cls, on=["store_id", "item_id"], how="left"
    )
    now = now.merge(
        table[["abc", "demand_class", "ss_ratio", "source"]],
        on=["abc", "demand_class"], how="left",
    )
    now["safety_stock"] = now["ss_ratio"] * now["level_7d"]
    now["reorder_point"] = now["forecast_7d"] + now["safety_stock"]
    now.to_parquet(config.PROCESSED_DIR / "policy_params.parquet", index=False)

    # Prints
    print(f"\nTest rows: {n_all:,}  kept (level > 0): {len(ev):,}")
    print("\nSafety stock as a share of weekly demand level:")
    print(table.round(3).to_string(index=False))

    ev = ev.merge(table[["abc", "demand_class", "ss_ratio"]], on=["abc", "demand_class"])
    ev["covered"] = ev["actual"] <= ev["forecast"] + ev["ss_ratio"] * ev["level"]
    print("\nShare of past 7-day windows covered (in-sample check):")
    print(ev.groupby("abc")["covered"].mean().round(3))

    print(f"\nSeries with a policy: {len(now):,}")
    print(f"Total 7-day forecast (units): {now['forecast_7d'].sum():,.0f}")
    print(f"Total safety stock (units):   {now['safety_stock'].sum():,.0f}")


if __name__ == "__main__":
    main()