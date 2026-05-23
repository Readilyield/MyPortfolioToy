from __future__ import annotations
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
STORAGE_DIR = PROJECT_ROOT / "storage"
PORTFOLIO_STATE_PATH = STORAGE_DIR / "portfolio_state.json"
RECOMMENDATION_LOG_PATH = STORAGE_DIR / "recommendation_log.csv"
EXECUTION_LOG_PATH = STORAGE_DIR / "execution_log.csv"
SNAPSHOT_LOG_PATH = STORAGE_DIR / "portfolio_snapshots.csv"
NASDAQ_PRICES_PATH = DATA_DIR / "nasdaq100_daily_5y.csv"
NDX_PRICES_PATH = DATA_DIR / "NDX_daily_5y.csv"
NASDAQ_TICKERS_PATH = DATA_DIR / "nasdaq100_tickers.csv"
DATA_METADATA_PATH = DATA_DIR / "market_data_metadata.json"
