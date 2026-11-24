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

MA_WINDOW = 28                                          # days in the moving average
SERVICE_LEVELS = {"A": 0.98, "B": 0.95, "C": 0.90}      # proposed, see assumptions
MIN_GROUP_ROWS = 500                                    # smaller groups use the ABC-level pool

TEST_DAYS = 224          # last 224 days are the backtest period
COGS_SHARE = 0.70        # B4: unit cost = 70% of selling price
HOLDING_RATE = 0.20      # B3: yearly holding cost, share of unit cost
ORDER_COST = 2.0         # B5: cost per order placed
BASELINE_DAYS = [7, 14, 21, 30, 45]   # baseline: reorder at N days of average sales
SERVICE_SETS = {
    "low": {"A": 0.95, "B": 0.90, "C": 0.85},
    "default": {"A": 0.98, "B": 0.95, "C": 0.90},
    "high": {"A": 0.995, "B": 0.99, "C": 0.95},
}