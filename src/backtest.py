import numpy as np
import pandas as pd
import config
from policy import load_store_matrix, forecasts_at, build_safety_table

COLS = ["demand", "sold", "inv_units", "inv_value", "orders", "lost_margin"]


def prepare(store, avail):
    items, y = load_store_matrix(store)
    a = avail[avail["store_id"] == store].set_index("item_id")
    start = a.loc[items, "first_price_day"].to_numpy().astype(int)
    csum = np.concatenate(
        [np.zeros((len(items), 1)), np.cumsum(y, axis=1, dtype=np.float64)], axis=1
    )
    return items, y, start, csum


def fit_tables(avail, cls, t0):
    """Safety stock ratios fitted ONLY on windows that ended before the test."""
    lead = config.LEAD_TIME_DAYS
    origins = [t0 - 1 - lead - config.ORIGIN_STEP * k for k in range(config.N_ORIGINS)]
    parts = []
    for store in sorted(avail["store_id"].unique()):
        items, y, start, csum = prepare(store, avail)
        for d in origins:
            n_hist, f, level = forecasts_at(csum, start, d)
            actual = csum[:, d + lead] - csum[:, d]
            ok = (n_hist >= config.MIN_HISTORY) & (level > 0)
            parts.append(pd.DataFrame({
                "store_id": store, "item_id": items[ok],
                "forecast": f[ok], "level": level[ok], "actual": actual[ok],
            }))
        print(f"fit {store}: done")
    ev = pd.concat(parts, ignore_index=True)
    ev["miss_ratio"] = (ev["actual"] - ev["forecast"]) / ev["level"]
    ev = ev.merge(cls, on=["store_id", "item_id"], how="left")
    return {n: build_safety_table(ev, lv) for n, lv in config.SERVICE_SETS.items()}


def simulate(y, start, price_day, F, L, rop_fn, t0):
    """Replay the test days for every series of one store under one policy."""
    n = y.shape[0]
    T, lead = config.TEST_DAYS, config.LEAD_TIME_DAYS
    on_hand = np.zeros(n)
    on_order = np.zeros(n)
    arrivals = np.zeros((n, T + lead + 1))
    started = np.zeros(n, dtype=bool)
    m = {c: np.zeros(n) for c in COLS}

    for i in range(T):
        t = t0 + i
        f, level = F[i], L[i]
        active = start <= t
        rop_raw = rop_fn(f, level)
        rop = np.ceil(rop_raw)                 # whole units only
        S = np.ceil(rop_raw + level)           # order up to: ROP + one normal week

        new = active & ~started                # first day on the shelf: start full
        on_hand[new] = S[new]
        started |= new

        on_hand += arrivals[:, i]              # deliveries
        on_order -= arrivals[:, i]

        demand = np.where(active, y[:, t - 1].astype(np.float64), 0.0)
        sold = np.minimum(on_hand, demand)     # lost sales, no backorders
        lost = demand - sold
        on_hand -= sold

        position = on_hand + on_order
        qty = np.where(active & (position <= rop), np.maximum(S - position, 0.0), 0.0)
        arrivals[:, i + lead] += qty
        on_order += qty

        price = price_day[:, t - 1].astype(np.float64)
        unit_cost = price * config.COGS_SHARE
        m["demand"] += demand
        m["sold"] += sold
        m["inv_units"] += np.where(active, on_hand, 0.0)
        m["inv_value"] += np.where(active, on_hand * unit_cost, 0.0)
        m["orders"] += (qty > 0)
        m["lost_margin"] += lost * price * (1 - config.COGS_SHARE)
    return m


def run_store(store, avail, cls, tables, all_prices, weeks, day_week_code, t0):
    items, y, start, csum = prepare(store, avail)
    n, T = len(items), config.TEST_DAYS
    lead = config.LEAD_TIME_DAYS

    # weekly price -> daily price matrix
    p = all_prices[all_prices["store_id"] == store]
    codes = pd.Categorical(p["item_id"], categories=items).codes
    mat = np.zeros((n, len(weeks)), dtype=np.float32)
    mat[codes, np.searchsorted(weeks, p["wm_yr_wk"].to_numpy())] = p["sell_price"].to_numpy()
    price_day = mat[:, day_week_code]

    # class labels and safety ratios per series
    c = cls[cls["store_id"] == store].set_index("item_id").loc[items]
    idx = pd.MultiIndex.from_arrays([c["abc"].to_numpy(), c["demand_class"].to_numpy()])
    ratio = {}
    for name, tb in tables.items():
        s = tb.set_index(["abc", "demand_class"])["ss_ratio"].reindex(idx)
        ratio[name] = s.fillna(tb["ss_ratio"].median()).to_numpy()

    # forecast and normal level for each test day (data up to that day only)
    F, L = np.zeros((T, n)), np.zeros((T, n))
    for i in range(T):
        _, F[i], L[i] = forecasts_at(csum, start, t0 + i)

    scenarios = {}
    for days in config.BASELINE_DAYS:
        scenarios[f"base_{days}d"] = lambda f, lv, days=days: days * lv / lead
    for name in tables:
        scenarios[f"ours_{name}"] = lambda f, lv, r=ratio[name]: f + r * lv

    out = []
    for sname, fn in scenarios.items():
        m = simulate(y, start, price_day, F, L, fn, t0)
        df = pd.DataFrame(m)
        df["store_id"], df["item_id"], df["scenario"] = store, items, sname
        out.append(df)
    return pd.concat(out, ignore_index=True)


def summarize(df, order_cost=None):
    order_cost = config.ORDER_COST if order_cost is None else order_cost
    g = df.groupby("scenario", sort=False)[COLS].sum()
    o = pd.DataFrame(index=g.index)
    o["fill_rate"] = g["sold"] / g["demand"]
    o["avg_stock_units"] = g["inv_units"] / config.TEST_DAYS
    o["avg_stock_value"] = g["inv_value"] / config.TEST_DAYS
    o["holding"] = g["inv_value"] * config.HOLDING_RATE / 365
    o["ordering"] = g["orders"] * order_cost
    o["lost_margin"] = g["lost_margin"]
    o["total_cost"] = o["holding"] + o["ordering"] + o["lost_margin"]
    return o


def main() -> None:
    cls = pd.read_parquet(
        config.PROCESSED_DIR / "item_classes.parquet",
        columns=["store_id", "item_id", "abc", "demand_class"],
    )
    avail = pd.read_parquet(
        config.PROCESSED_DIR / "avalability.parquet",
        columns=["store_id", "item_id", "first_price_day"],
    )
    calendar = pd.read_parquet(config.PROCESSED_DIR / "calendar.parquet")
    calendar["d_num"] = calendar["d"].str.slice(2).astype(int)
    weeks = np.sort(calendar["wm_yr_wk"].unique())
    cal = calendar.sort_values("d_num")
    day_week_code = np.searchsorted(weeks, cal["wm_yr_wk"].to_numpy()[: config.N_DAYS])

    all_prices = pd.read_parquet(config.PROCESSED_DIR / "weekly_pricess.parquet")
    all_prices["store_id"] = all_prices["store_id"].astype(str)
    all_prices["item_id"] = all_prices["item_id"].astype(str)

    t0 = config.N_DAYS - config.TEST_DAYS + 1
    tables = fit_tables(avail, cls, t0)

    parts = []
    for store in sorted(avail["store_id"].unique()):
        parts.append(run_store(store, avail, cls, tables, all_prices, weeks, day_week_code, t0))
        print(f"backtest {store}: done")

    res = pd.concat(parts, ignore_index=True)
    res = res.merge(cls[["store_id", "item_id", "abc"]], on=["store_id", "item_id"], how="left")
    res.to_parquet(config.PROCESSED_DIR / "backtest_series.parquet", index=False)

    print(f"\nBacktest days: {t0} to {config.N_DAYS}  Series: {res['item_id'].size // len(res['scenario'].unique()):,}")
    print("\nAll series (order cost = $%.1f):" % config.ORDER_COST)
    print(summarize(res).round(3).to_string())

    print("\nTotal cost under different order costs:")
    print(pd.DataFrame({c: summarize(res, c)["total_cost"] for c in [0, 2, 10]}).round(0).to_string())

    for abc in ["A", "B", "C"]:
        sub = res[(res["abc"] == abc) & res["scenario"].isin(["base_30d", "ours_default"])]
        print(f"\nClass {abc}:")
        print(summarize(sub)[["fill_rate", "avg_stock_value", "total_cost"]].round(3).to_string())


if __name__ == "__main__":
    main()