from __future__ import annotations

from pathlib import Path
import pandas as pd
try:
    import yfinance as yf
except Exception:  # optional dependency at runtime
    yf = None

from src.paths import NASDAQ_PRICES_PATH, NDX_PRICES_PATH, NASDAQ_TICKERS_PATH, SUPPLEMENTAL_PRICES_PATH
from src.utils import read_price_data, make_close_price_matrix


def load_price_matrix(csv_path: str | Path = NASDAQ_PRICES_PATH) -> pd.DataFrame:
    """Load long-form ticker data and return a date-by-ticker close-price matrix."""
    df = read_price_data(str(csv_path))
    prices = make_close_price_matrix(df)
    return prices.dropna(axis=1, how="all").sort_index()


def load_ndx_series(csv_path: str | Path = NDX_PRICES_PATH) -> pd.Series:
    """Load the NDX benchmark close series."""
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    close_col = "close" if "close" in df.columns else df.columns[-1]
    return df.set_index("date")[close_col].rename("NDX")


def normalize_ticker(symbol: str) -> str:
    """Normalize user-entered tickers into Yahoo-compatible uppercase symbols."""
    return str(symbol).strip().upper().replace(".", "-")


def load_ticker_universe(csv_path: str | Path = NASDAQ_PRICES_PATH) -> list[str]:
    """Return all tickers in the local NASDAQ-100 strategy universe.

    This is the universe the strategy is allowed to buy/sell. It is intentionally
    separate from the tracking universe, which may contain ETFs or non-NASDAQ-100
    corporate stocks from the user's existing holdings.
    """
    ticker_path = Path(NASDAQ_TICKERS_PATH)
    if ticker_path.exists():
        tickers = pd.read_csv(ticker_path)
        if "ticker" in tickers.columns and not tickers.empty:
            return sorted(tickers["ticker"].dropna().astype(str).map(normalize_ticker).unique().tolist())
    df = pd.read_csv(csv_path, usecols=["ticker"])
    return sorted(df["ticker"].dropna().astype(str).map(normalize_ticker).unique().tolist())


def latest_prices(price_matrix: pd.DataFrame) -> pd.Series:
    """Return the latest available close for every ticker."""
    if price_matrix.empty:
        return pd.Series(dtype=float)
    return price_matrix.ffill().iloc[-1].dropna()


def load_supplemental_price_matrix(csv_path: str | Path = SUPPLEMENTAL_PRICES_PATH) -> pd.DataFrame:
    """Load locally stored prices for user-tracked non-NASDAQ-100 tickers.

    The file lives under storage/ because the ticker list can reveal private
    holdings. The folder is ignored by Git.
    """
    p = Path(csv_path)
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame()
    df = read_price_data(str(p))
    prices = make_close_price_matrix(df)
    return prices.dropna(axis=1, how="all").sort_index()


def load_tracking_price_matrix(extra_tickers: list[str] | set[str] | None = None) -> pd.DataFrame:
    """Load prices for portfolio tracking.

    This combines the public NASDAQ-100 strategy data with private, local-only
    supplemental ticker prices from storage/supplemental_daily_prices.csv.
    """
    base = load_price_matrix(NASDAQ_PRICES_PATH)
    supplemental = load_supplemental_price_matrix(SUPPLEMENTAL_PRICES_PATH)
    if supplemental.empty:
        combined = base.copy()
    else:
        combined = pd.concat([base, supplemental], axis=1)
        combined = combined.loc[:, ~combined.columns.duplicated(keep="last")].sort_index()
    if extra_tickers:
        # Keep all available data, but add empty columns for missing held tickers so
        # downstream tables can tell the user exactly which prices are missing.
        for ticker in sorted({normalize_ticker(t) for t in extra_tickers if str(t).strip()}):
            if ticker not in combined.columns:
                combined[ticker] = pd.NA
    return combined.sort_index()
