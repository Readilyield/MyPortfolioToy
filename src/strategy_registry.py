from __future__ import annotations
from typing import Callable, Dict, Any
import pandas as pd

from src import portfolio_strategies as ps

StrategyFactory = Callable[..., Callable[[pd.DataFrame, pd.Timestamp], pd.Series]]

STRATEGY_FACTORIES: dict[str, StrategyFactory] = {
    "Top-K Momentum": ps.benchmark_topk_momentum,
    "Trend-Filtered Top-K Momentum": ps.trend_filtered_topk_momentum,
    "Momentum with Pullback": ps.momentum_with_pullback,
    "Inverse-Volatility Momentum": ps.topk_momentum_inverse_vol,
    "Low-Volatility Momentum": ps.low_vol_momentum_filter,
    "Defensive Momentum": ps.defensive_topk_momentum,
    "SMA Cross": ps.benchmark_sma_cross,
}

DEFAULT_STRATEGY_PARAMS: dict[str, dict[str, Any]] = {
    "Top-K Momentum": {"lookback": 30, "top_k": 10},
    "Trend-Filtered Top-K Momentum": {"lookback": 90, "top_k": 10, "vol_window": 20, "stock_ma_window": 100, "market_ma_window": 150},
    "Momentum with Pullback": {"lookback": 90, "short_lookback": 5, "top_k": 10, "vol_window": 20, "stock_ma_window": 100},
    "Inverse-Volatility Momentum": {"lookback": 30, "top_k": 10, "vol_window": 20},
    "Low-Volatility Momentum": {"lookback": 60, "top_k": 10, "vol_window": 20},
    "Defensive Momentum": {"lookback": 30, "top_k": 10, "market_filter_window": 100},
    "SMA Cross": {"short_window": 20, "long_window": 50},
}


def build_strategy(name: str, params: dict[str, Any] | None = None):
    if name not in STRATEGY_FACTORIES:
        raise KeyError(f"Unknown strategy: {name}")
    merged = DEFAULT_STRATEGY_PARAMS.get(name, {}).copy()
    if params:
        merged.update(params)
    return STRATEGY_FACTORIES[name](**merged)
