"""Single-stock trading strategies.

Each strategy returns a weight series over all tickers, but only one ticker
gets a positive weight. This keeps the interface consistent with the general
backtester.
"""

from __future__ import annotations

import pandas as pd



def _empty_weights(history: pd.DataFrame) -> pd.Series:
    return pd.Series(0.0, index=history.columns)



def single_stock_momentum(ticker: str, lookback: int = 20, invest_weight: float = 1.0):
    """Buy if the trailing return is positive."""

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        weights = _empty_weights(history)
        prices = history[ticker].dropna()
        if len(prices) < lookback + 1:
            return weights
        trailing_return = prices.iloc[-1] / prices.iloc[-lookback - 1] - 1.0
        if trailing_return > 0:
            weights[ticker] = invest_weight
        return weights

    return strategy



def single_stock_mean_reversion(ticker: str, lookback: int = 5, threshold: float = -0.03, invest_weight: float = 1.0):
    """Buy after a short-term drop, expecting a bounce."""

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        weights = _empty_weights(history)
        prices = history[ticker].dropna()
        if len(prices) < lookback + 1:
            return weights
        trailing_return = prices.iloc[-1] / prices.iloc[-lookback - 1] - 1.0
        if trailing_return < threshold:
            weights[ticker] = invest_weight
        return weights

    return strategy



def single_stock_sma_crossover(ticker: str, short_window: int = 20, long_window: int = 50, invest_weight: float = 1.0):
    """Buy when short moving average is above long moving average."""

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        weights = _empty_weights(history)
        prices = history[ticker].dropna()
        if len(prices) < long_window:
            return weights
        short_ma = prices.tail(short_window).mean()
        long_ma = prices.tail(long_window).mean()
        if short_ma > long_ma:
            weights[ticker] = invest_weight
        return weights

    return strategy



def single_stock_breakout(ticker: str, lookback: int = 20, invest_weight: float = 1.0):
    """Buy when today's close is the highest over the recent window."""

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        weights = _empty_weights(history)
        prices = history[ticker].dropna()
        if len(prices) < lookback:
            return weights
        recent_max = prices.tail(lookback).max()
        if prices.iloc[-1] >= recent_max:
            weights[ticker] = invest_weight
        return weights

    return strategy



def single_stock_low_vol_momentum(ticker: str, lookback: int = 20, vol_window: int = 20, max_vol: float = 0.025, invest_weight: float = 1.0):
    """Buy only if momentum is positive and recent volatility is not too high."""

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        weights = _empty_weights(history)
        prices = history[ticker].dropna()
        if len(prices) < max(lookback + 1, vol_window + 1):
            return weights
        trailing_return = prices.iloc[-1] / prices.iloc[-lookback - 1] - 1.0
        daily_returns = prices.pct_change().dropna().tail(vol_window)
        realized_vol = daily_returns.std(ddof=0)
        if trailing_return > 0 and realized_vol <= max_vol:
            weights[ticker] = invest_weight
        return weights

    return strategy
