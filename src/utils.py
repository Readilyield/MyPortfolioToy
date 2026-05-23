"""Utility functions for Course Project 1.

This file keeps the data loading and reshaping logic simple and readable.
"""

from __future__ import annotations

import pandas as pd



def read_price_data(csv_path: str) -> pd.DataFrame:
    """Read the raw CSV file and return a clean long-form dataframe.

    Expected columns in the CSV:
    ticker, date, open, high, low, close, volume
    """
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "ticker"]).reset_index(drop=True)
    return df



def make_long_form_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of the input in long-form structure.

    The provided CSV is already in long form, but this function is kept
    so users have a standard entry point for the project.
    """
    cols = ["ticker", "date", "open", "high", "low", "close", "volume"]
    return df[cols].copy().sort_values(["date", "ticker"]).reset_index(drop=True)



def make_close_price_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Convert long-form data into a date x ticker close-price matrix."""
    price_matrix = df.pivot(index="date", columns="ticker", values="close")
    price_matrix = price_matrix.sort_index().sort_index(axis=1)
    return price_matrix



def make_volume_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Convert long-form data into a date x ticker volume matrix."""
    volume_matrix = df.pivot(index="date", columns="ticker", values="volume")
    volume_matrix = volume_matrix.sort_index().sort_index(axis=1)
    return volume_matrix



def compute_daily_returns(price_matrix: pd.DataFrame) -> pd.DataFrame:
    """Compute simple daily returns from close prices."""
    returns = price_matrix.pct_change(fill_method=None).fillna(0.0)
    return returns



def get_single_ticker_prices(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Return the historical rows for one ticker."""
    out = df[df["ticker"] == ticker].copy()
    out = out.sort_values("date").reset_index(drop=True)
    return out



def normalize_weights(weights: pd.Series, max_gross: float = 1.0) -> pd.Series:
    """Clean portfolio weights to satisfy project constraints.

    Rules enforced:
    - no short selling
    - no leverage
    - total weight <= max_gross
    """
    weights = weights.fillna(0.0).clip(lower=0.0)
    total = weights.sum()
    if total > max_gross and total > 0:
        weights = weights / total * max_gross
    return weights



def to_long_weights(weights_df: pd.DataFrame) -> pd.DataFrame:
    """Convert a wide weight table to long form for logging or inspection."""
    out = weights_df.stack().reset_index()
    out.columns = ["date", "ticker", "weight"]
    return out
