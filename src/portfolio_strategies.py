"""
Portfolio-level trading strategies.

These strategies work on the full stock universe and return a target weight
for every ticker.
"""

from __future__ import annotations

import pandas as pd

from src.utils import normalize_weights



def equal_weight_selected(selected_tickers: list[str], all_tickers: list[str]) -> pd.Series:
    """Assign equal weights to the selected tickers."""
    weights = pd.Series(0.0, index=all_tickers)
    if len(selected_tickers) == 0:
        return weights
    weights.loc[selected_tickers] = 1.0 / len(selected_tickers)
    return normalize_weights(weights)



def inverse_vol_weight_selected(selected_tickers: list[str], returns_window: pd.DataFrame, all_tickers: list[str]) -> pd.Series:
    """Assign weights inversely proportional to recent volatility."""
    weights = pd.Series(0.0, index=all_tickers)
    if len(selected_tickers) == 0:
        return weights

    vols = returns_window[selected_tickers].std(ddof=0).replace(0.0, pd.NA)
    inv_vol = 1.0 / vols
    inv_vol = inv_vol.fillna(0.0)
    if inv_vol.sum() == 0:
        return equal_weight_selected(selected_tickers, all_tickers)

    weights.loc[selected_tickers] = inv_vol / inv_vol.sum()
    return normalize_weights(weights)



def benchmark_sma_cross(short_window: int = 20, long_window: int = 50):
    """
    Benchmark 1 from the project description.
    Select stocks with short SMA above long SMA, then equal-weight them.
    """

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        tickers = list(history.columns)
        if len(history) < long_window:
            return pd.Series(0.0, index=tickers)

        short_ma = history.tail(short_window).mean()
        long_ma = history.tail(long_window).mean()
        selected = list(short_ma[short_ma > long_ma].index)
        return equal_weight_selected(selected, tickers)

    return strategy



def benchmark_topk_momentum(lookback: int = 30, top_k: int = 10):
    """
    Benchmark 2 from the project description.
    Rank stocks by trailing return and equal-weight the top K.
    """

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        tickers = list(history.columns)
        if len(history) < lookback + 1:
            return pd.Series(0.0, index=tickers)

        trailing_returns = history.iloc[-1] / history.iloc[-lookback - 1] - 1.0
        selected = list(trailing_returns.nlargest(top_k).index)
        return equal_weight_selected(selected, tickers)

    return strategy



def topk_momentum_inverse_vol(lookback: int = 30, top_k: int = 10, vol_window: int = 20):
    """A stronger variation of momentum using inverse-volatility weighting."""

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        tickers = list(history.columns)
        if len(history) < max(lookback + 1, vol_window + 1):
            return pd.Series(0.0, index=tickers)

        trailing_returns = history.iloc[-1] / history.iloc[-lookback - 1] - 1.0
        selected = list(trailing_returns.nlargest(top_k).index)
        returns_window = history.pct_change(fill_method=None).dropna().tail(vol_window)
        return inverse_vol_weight_selected(selected, returns_window, tickers)

    return strategy



def low_vol_momentum_filter(lookback: int = 60, top_k: int = 10, vol_window: int = 20):
    """Select high-momentum stocks only from the lower-volatility half of the universe."""

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        tickers = list(history.columns)
        if len(history) < max(lookback + 1, vol_window + 1):
            return pd.Series(0.0, index=tickers)

        trailing_returns = history.iloc[-1] / history.iloc[-lookback - 1] - 1.0
        vol = history.pct_change(fill_method=None).dropna().tail(vol_window).std(ddof=0)
        low_vol_names = list(vol.nsmallest(max(len(vol) // 2, top_k)).index)
        scores = trailing_returns.loc[low_vol_names]
        selected = list(scores.nlargest(top_k).index)
        return equal_weight_selected(selected, tickers)

    return strategy



def mean_reversion_bounce(lookback: int = 5, top_k: int = 10):
    """Buy the biggest recent losers, equally weighted."""

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        tickers = list(history.columns)
        if len(history) < lookback + 1:
            return pd.Series(0.0, index=tickers)

        trailing_returns = history.iloc[-1] / history.iloc[-lookback - 1] - 1.0
        selected = list(trailing_returns.nsmallest(top_k).index)
        return equal_weight_selected(selected, tickers)

    return strategy



def defensive_topk_momentum(lookback: int = 30, top_k: int = 10, market_filter_window: int = 100):
    """
    Hold top-K momentum names only when the market trend is positive.
    The market proxy is the average close price across all stocks.
    """

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        tickers = list(history.columns)
        if len(history) < max(lookback + 1, market_filter_window):
            return pd.Series(0.0, index=tickers)

        market_proxy = history.mean(axis=1)
        short_ma = market_proxy.tail(20).mean()
        long_ma = market_proxy.tail(market_filter_window).mean()
        if short_ma <= long_ma:
            return pd.Series(0.0, index=tickers)

        trailing_returns = history.iloc[-1] / history.iloc[-lookback - 1] - 1.0
        selected = list(trailing_returns.nlargest(top_k).index)
        return equal_weight_selected(selected, tickers)

    return strategy



#########################
#########################
'''Two New Strategies'''
#########################
#########################


def trend_filtered_topk_momentum(lookback: int = 90, top_k: int = 10, vol_window: int = 20, stock_ma_window: int = 100, market_ma_window: int = 150):
    """
    Top-K momentum with both market and stock trend filters.
    
    Idea:
    1. Only invest when the broad market looks healthy.
    2. Only consider stocks that are above their own moving average.
    3. Among those stocks, buy the strongest medium-term winners.
    4. Use inverse-volatility weights to reduce concentration in very volatile names.
    """

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        tickers = list(history.columns)
        min_history = max(lookback + 1, vol_window + 1, stock_ma_window, market_ma_window)
        if len(history) < min_history:
            return pd.Series(0.0, index=tickers)

        # Use the average close across all stocks as a simple market proxy.
        market_proxy = history.mean(axis=1)
        market_short_ma = market_proxy.tail(20).mean()
        market_long_ma = market_proxy.tail(market_ma_window).mean()
        if market_short_ma <= market_long_ma:
            return pd.Series(0.0, index=tickers)

        current_prices = history.iloc[-1]
        stock_long_ma = history.tail(stock_ma_window).mean()
        eligible = list(current_prices[current_prices > stock_long_ma].index)
        if len(eligible) == 0:
            return pd.Series(0.0, index=tickers)

        trailing_returns = history.iloc[-1] / history.iloc[-lookback - 1] - 1.0
        scores = trailing_returns.loc[eligible]
        selected = list(scores.nlargest(min(top_k, len(scores))).index)
        returns_window = history.pct_change(fill_method=None).dropna().tail(vol_window)
        return inverse_vol_weight_selected(selected, returns_window, tickers)

    return strategy


def momentum_with_pullback(lookback: int = 90, short_lookback: int = 5, top_k: int = 10, vol_window: int = 20, stock_ma_window: int = 100):
    """
    Pick strong medium-term winners that also had a small recent pullback.

    Idea:
    - We still want stocks with good medium-term momentum.
    - But instead of buying the ones that already surged the most in the last few days,
      we slightly penalize very recent returns.
    - This can help avoid potential FOMO right after a short-term spike.
    """

    def strategy(history: pd.DataFrame, current_date: pd.Timestamp) -> pd.Series:
        tickers = list(history.columns)
        min_history = max(lookback + 1, short_lookback + 1, vol_window + 1, stock_ma_window)
        if len(history) < min_history:
            return pd.Series(0.0, index=tickers)

        current_prices = history.iloc[-1]
        stock_long_ma = history.tail(stock_ma_window).mean()
        eligible = list(current_prices[current_prices > stock_long_ma].index)
        if len(eligible) == 0:
            return pd.Series(0.0, index=tickers)

        medium_term_return = history.iloc[-1] / history.iloc[-lookback - 1] - 1.0
        recent_return = history.iloc[-1] / history.iloc[-short_lookback - 1] - 1.0

        # High score = strong medium-term trend, but not too overheated very recently.
        scores = (medium_term_return - 0.5 * recent_return).loc[eligible]
        selected = list(scores.nlargest(min(top_k, len(scores))).index)
        returns_window = history.pct_change(fill_method=None).dropna().tail(vol_window)
        return inverse_vol_weight_selected(selected, returns_window, tickers)

    return strategy
