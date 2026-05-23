from __future__ import annotations

from pathlib import Path
import pandas as pd
try:
    import yfinance as yf
except Exception:  # optional dependency at runtime
    yf = None

from src.paths import NASDAQ_PRICES_PATH, NDX_PRICES_PATH
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


def load_ticker_universe(csv_path: str | Path = NASDAQ_PRICES_PATH) -> list[str]:
    """Return all tickers in the local NASDAQ-100 dataset."""
    df = pd.read_csv(csv_path, usecols=["ticker"])
    return sorted(df["ticker"].dropna().unique().tolist())


def latest_prices(price_matrix: pd.DataFrame) -> pd.Series:
    """Return the latest available close for every ticker."""
    if price_matrix.empty:
        return pd.Series(dtype=float)
    return price_matrix.ffill().iloc[-1].dropna()


def refresh_prices_with_yfinance(tickers: list[str], period: str = "5y") -> pd.DataFrame:
    """Download adjusted close prices from Yahoo Finance through yfinance.

    This function is optional. The app works with local CSV data without calling it.
    """
    if yf is None:
        raise ImportError("yfinance is not installed. Install it or use local CSV data.")
    data = yf.download(tickers, period=period, auto_adjust=False, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        if "Close" in data.columns.get_level_values(0):
            close = data["Close"]
        else:
            close = data.xs("Close", axis=1, level=1)
    else:
        close = data[["Close"]].rename(columns={"Close": tickers[0]})
    return close.dropna(how="all").sort_index()
