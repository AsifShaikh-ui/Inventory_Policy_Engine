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

ADI_CUTOFF = 1.32
CV2_CUTOFF = 0.49
ABC_A_SHARE = 0.80
ABC_B_SHARE = 0.95

LEAD_TIME_DAYS = 7        # assumption B1
N_ORIGINS = 8             # number of test cut-off dates
ORIGIN_STEP = 28          # days between cut-off dates
MIN_HISTORY = 56          # available days needed before a cut-off
SAMPLE_PER_GROUP = 80     # series sampled per ABC x demand class
SMOOTHING_ALPHA = 0.1     # starting value, not tuned
TSB_BETA = 0.1            # starting value, not tuned