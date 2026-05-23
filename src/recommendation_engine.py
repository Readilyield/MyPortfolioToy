from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

from src.portfolio_state import PortfolioState, portfolio_value
from src.paths import RECOMMENDATION_LOG_PATH, STORAGE_DIR
from src.strategy_registry import build_strategy
from src.utils import normalize_weights


def cap_weights(weights: pd.Series, max_allocation_per_stock: float = 0.20) -> pd.Series:
    weights = weights.fillna(0.0).clip(lower=0.0)
    if max_allocation_per_stock and max_allocation_per_stock > 0:
        weights = weights.clip(upper=max_allocation_per_stock)
    return normalize_weights(weights)


def volatility_adjusted_price_band(price_history: pd.DataFrame, ticker: str, minimum_pct: float = 0.01, vol_window: int = 20) -> float:
    if ticker not in price_history.columns or len(price_history) < vol_window + 1:
        return minimum_pct
    rets = price_history[ticker].pct_change(fill_method=None).dropna().tail(vol_window)
    if rets.empty:
        return minimum_pct
    band = 0.5 * float(rets.std(ddof=0))
    return max(minimum_pct, band)


def compute_target_weights(price_history: pd.DataFrame, strategy_name: str, strategy_params: dict | None = None, max_allocation_per_stock: float = 0.20) -> pd.Series:
    if price_history.empty:
        return pd.Series(dtype=float)
    current_date = price_history.index[-1]
    strategy = build_strategy(strategy_name, strategy_params)
    weights = strategy(price_history, current_date).reindex(price_history.columns).fillna(0.0)
    return cap_weights(weights, max_allocation_per_stock=max_allocation_per_stock)


def generate_recommendations(
    state: PortfolioState,
    price_history: pd.DataFrame,
    strategy_name: str | None = None,
    strategy_params: dict | None = None,
    max_allocation_per_stock: float = 0.20,
    min_trade_value: float = 50.0,
    minimum_price_band_pct: float = 0.01,
    integer_shares: bool = True,
) -> pd.DataFrame:
    """Convert strategy target weights into one buy/sell/hold row per relevant stock."""
    if price_history.empty:
        return pd.DataFrame()

    strategy_name = strategy_name or state.strategy
    target_weights = compute_target_weights(price_history, strategy_name, strategy_params, max_allocation_per_stock)
    prices = price_history.ffill().iloc[-1].dropna()
    total_value = portfolio_value(state, prices)

    rows = []
    universe = sorted(set(prices.index).union(state.holdings.keys()).union(target_weights.index))
    for ticker in universe:
        price = float(prices.get(ticker, np.nan))
        if not np.isfinite(price) or price <= 0:
            continue
        current_shares = float(state.holdings.get(ticker).shares) if ticker in state.holdings else 0.0
        target_weight = float(target_weights.get(ticker, 0.0))
        current_value = current_shares * price
        target_value = total_value * target_weight
        raw_target_shares = target_value / price
        target_shares = np.floor(raw_target_shares) if integer_shares else raw_target_shares
        share_delta = float(target_shares - current_shares)
        trade_value = abs(share_delta) * price

        if trade_value < min_trade_value:
            action = "HOLD"
            share_delta = 0.0
        elif share_delta > 0:
            action = "BUY"
        elif share_delta < 0:
            action = "SELL"
        else:
            action = "HOLD"

        band_pct = volatility_adjusted_price_band(price_history, ticker, minimum_pct=minimum_price_band_pct)
        rows.append({
            "date": price_history.index[-1].date().isoformat(),
            "ticker": ticker,
            "action": action,
            "current_shares": current_shares,
            "target_shares": float(target_shares),
            "share_delta": share_delta,
            "latest_price": price,
            "price_range_low": price * (1 - band_pct) if action != "HOLD" else np.nan,
            "price_range_high": price * (1 + band_pct) if action != "HOLD" else np.nan,
            "current_value": current_value,
            "target_value": target_value,
            "current_weight": current_value / total_value if total_value > 0 else 0.0,
            "target_weight": target_weight,
            "estimated_cash_impact": -share_delta * price,
            "strategy": strategy_name,
            "status": "pending" if action != "HOLD" else "hold",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    order = {"BUY": 0, "SELL": 1, "HOLD": 2}
    out["action_order"] = out["action"].map(order).fillna(3)
    return out.sort_values(["action_order", "ticker"]).drop(columns=["action_order"]).reset_index(drop=True)


def load_recommendation_log(path: str | Path = RECOMMENDATION_LOG_PATH) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


def save_daily_recommendations(recommendations: pd.DataFrame, path: str | Path = RECOMMENDATION_LOG_PATH) -> pd.DataFrame:
    """Save at most one recommendation per date/ticker, replacing today's prior rows."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    if recommendations.empty:
        return recommendations
    p = Path(path)
    today_keys = recommendations[["date", "ticker"]].copy()
    old = pd.read_csv(p) if p.exists() else pd.DataFrame()
    if not old.empty:
        old_key = old["date"].astype(str) + "|" + old["ticker"].astype(str)
        new_key = today_keys["date"].astype(str) + "|" + today_keys["ticker"].astype(str)
        old = old[~old_key.isin(set(new_key))]
        combined = pd.concat([old, recommendations], ignore_index=True)
    else:
        combined = recommendations.copy()
    combined.to_csv(p, index=False)
    return combined
