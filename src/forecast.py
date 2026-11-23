import numpy as np
import pandas as pd
import config

METHODS = ["zero", "ma28", "ma90", "sba", "tsb"]

def sample_series() -> pd.DataFrame:
    cls = pd.read_parquet(
        config.PROCESSED_DIR / "item_classes.parquet",
        columns=["store_id", "item_id", "abc", "demand_class"],
    )
    parts = [
        g.sample(min(len(g), config.SAMPLE_PER_GROUP), random_state=42)
        for _, g in cls.groupby(["abc", "demand_class"])
    ]
    return pd.concat(parts, ignore_index=True)

def load_sales(sample: pd.DataFrame) -> dict:
    """Daily units per sampled series, as arrays of length N_DAYS."""
    series = {}
    for store, grp in sample.groupby("store_id"):
        items = list(grp["item_id"])
        df = pd.read_parquet(
            config.INTERIM_DIR / "sales_long" / f"{store}.parquet",
            columns=["item_id", "d", "units_sold"],
        )
        df["item_id"] = df["item_id"].astype(str)
        df = df[df["item_id"].isin(items)].copy()
        df["d_num"] = df["d"].astype(str).str.slice(2).astype(int)
        for item, g in df.groupby("item_id"):
            arr = np.zeros(config.N_DAYS)
            arr[g["d_num"].to_numpy() - 1] = g["units_sold"].to_numpy()
            series[(store, item)] = arr
        print(f"{store}: loaded")
    return series


def load_sales(sample: pd.DataFrame) -> dict:
    """Daily units per sampled series, as arrays of length N_DAYS."""
    series = {}
    for store, grp in sample.groupby("store_id"):
        items = list(grp["item_id"])
        df = pd.read_parquet(
            config.INTERIM_DIR / "sales_long" / f"{store}.parquet",
            columns=["item_id", "d", "units_sold"],
        )
        df["item_id"] = df["item_id"].astype(str)
        df = df[df["item_id"].isin(items)].copy()
        df["d_num"] = df["d"].astype(str).str.slice(2).astype(int)
        for item, g in df.groupby("item_id"):
            arr = np.zeros(config.N_DAYS)
            arr[g["d_num"].to_numpy() - 1] = g["units_sold"].to_numpy()
            series[(store, item)] = arr
        print(f"{store}: loaded")
    return series


def forecast_series(y: np.ndarray, start: int, origins: list) -> list:
    """One pass through time. Returns one row per valid cut-off date."""
    a, b, lead = config.SMOOTHING_ALPHA, config.TSB_BETA, config.LEAD_TIME_DAYS
    csum = np.concatenate([[0.0], np.cumsum(y)])  # csum[d] = units in days 1..d
    origin_set = set(origins)

    # Croston / SBA state
    z = p = None
    q = 0
    # TSB state, started from the first 28 available days
    first = y[start - 1 : start - 1 + 28]
    tsb_p = float((first > 0).mean())
    pos = first[first > 0]
    tsb_z = float(pos.mean()) if len(pos) else 1.0

    rows = []
    for d in range(start, max(origins) + 1):
        v = y[d - 1]
        q += 1
        if v > 0:
            if z is None:
                z, p = v, q
            else:
                z += a * (v - z)
                p += a * (q - p)
            q = 0
            tsb_z += b * (v - tsb_z)
        tsb_p += a * (float(v > 0) - tsb_p)

        if d in origin_set:
            n_hist = d - start + 1
            if n_hist < config.MIN_HISTORY:
                continue
            w90 = min(90, n_hist)
            rows.append({
                "origin": d,
                "actual": csum[d + lead] - csum[d],
                "f_zero": 0.0,
                "f_ma28": lead * (csum[d] - csum[d - 28]) / 28,
                "f_ma90": lead * (csum[d] - csum[d - w90]) / w90,
                "f_sba": lead * (1 - a / 2) * z / p if z is not None else 0.0,
                "f_tsb": lead * tsb_p * tsb_z,
            })
    return rows


def score(df: pd.DataFrame) -> pd.DataFrame:
    total = df["actual"].sum()
    out = {}
    for m in METHODS:
        err = df[f"f_{m}"] - df["actual"]
        out[m] = {"wape": err.abs().sum() / total, "bias": err.sum() / total}
    return pd.DataFrame(out).T.round(3)


def main() -> None:
    sample = sample_series()
    avail = pd.read_parquet(config.PROCESSED_DIR / "avalability.parquet")
    start_of = avail.set_index(["store_id", "item_id"])["first_price_day"]

    sales = load_sales(sample)
    origins = [
        config.N_DAYS - config.LEAD_TIME_DAYS - config.ORIGIN_STEP * k
        for k in range(config.N_ORIGINS)
    ]

    meta = sample.set_index(["store_id", "item_id"])
    out = []
    for (store, item), y in sales.items():
        start = int(start_of[(store, item)])
        for r in forecast_series(y, start, origins):
            r.update(
                store_id=store,
                item_id=item,
                abc=meta.loc[(store, item), "abc"],
                demand_class=meta.loc[(store, item), "demand_class"],
            )
            out.append(r)

    ev = pd.DataFrame(out)
    ev.to_parquet(config.PROCESSED_DIR / "forecast_eval.parquet", index=False)

    print(f"Series: {len(sales):,}  Test rows: {len(ev):,}")
    print("\nOverall (7-day totals):")
    print(score(ev))
    for cls, g in ev.groupby("demand_class"):
        print(f"\nDemand class: {cls}")
        print(score(g))


if __name__ == "__main__":
    main()