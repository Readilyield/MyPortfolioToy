from __future__ import annotations
from typing import Callable, Dict, Any
import pandas as pd

from src import portfolio_strategies as ps

StrategyFactory = Callable[..., Callable[[pd.DataFrame, pd.Timestamp], pd.Series]]

STRATEGY_FACTORIES: dict[str, StrategyFactory] = {
    "Top-K Momentum": ps.benchmark_topk_momentum,
    "Trend-Filtered Top-K Momentum": ps.trend_filtered_topk_momentum,
    "Momentum with Pullback": ps.momentum_with_pullback,
}

DEFAULT_STRATEGY_PARAMS: dict[str, dict[str, Any]] = {
    "Top-K Momentum": {"lookback": 30, "top_k": 10},
    "Trend-Filtered Top-K Momentum": {"lookback": 90, "top_k": 10, "vol_window": 20, "stock_ma_window": 100, "market_ma_window": 150},
    "Momentum with Pullback": {"lookback": 90, "short_lookback": 5, "top_k": 10, "vol_window": 20, "stock_ma_window": 100},
}


def build_strategy(name: str, params: dict[str, Any] | None = None):
    if name not in STRATEGY_FACTORIES:
        raise KeyError(f"Unknown strategy: {name}")
    merged = DEFAULT_STRATEGY_PARAMS.get(name, {}).copy()
    if params:
        merged.update(params)
    return STRATEGY_FACTORIES[name](**merged)
