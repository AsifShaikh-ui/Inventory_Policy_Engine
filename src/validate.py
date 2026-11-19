import pandas as pd
import config

def main() -> None:

    files = sorted((config.INTERIM_DIR / "sales_long").glob("*.parquet"))
    assert len(files) == 10, f"Expected 10 stores files, found {len(files)}"

    total_rows = 0
    for f in files:
        df = pd.read_parquet(f)
        assert df.isna().sum().sum() == 0, f"Nulls found in {f.name}"
        assert (df["units_sold"] >= 0).all(), f"Negative sales in {f.name}"
        total_rows += len(df)

    assert total_rows == config.EXPECTED_SALES_ROWS, (
        f"Row Count {total_rows:,} != expected {config.EXPECTED_SALES_ROWS:,} "
    )
    print(f"OK: {total_rows:,} rows across {len(files)} stores, no nulls, no negatives")

if __name__ == "__main__":
    main()