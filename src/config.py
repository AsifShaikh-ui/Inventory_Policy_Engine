# This file is made for the paths, constants, assumption values

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = ROOT / "data" / "raw"
INTERIM_DIR =  ROOT / "data" / "interim"
PROCESSED_DIR =  ROOT / "data" / "processed"

SALES_FILE = RAW_DIR / "sales_train_evaluation.csv"
CALENDAR_FILE = RAW_DIR / "calendar.csv"
PRICE_FILE = RAW_DIR / "sell_prices.csv"

N_SERIES = 30490
N_DAYS = 1941
EXPECTED_SALES_ROWS = N_SERIES * N_DAYS

ITEM_COLS = ["item_id", "dept_id", "cat_id"]
STORE_COLS = ["store_id", "state_id"]