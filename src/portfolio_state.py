from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.paths import PORTFOLIO_STATE_PATH, STORAGE_DIR, SNAPSHOT_LOG_PATH


@dataclass
class Holding:
    shares: float = 0.0
    average_cost: float | None = None


@dataclass
class PortfolioState:
    cash: float = 0.0
    holdings: dict[str, Holding] = field(default_factory=dict)
    strategy: str = "Top-K Momentum"
    settings: dict[str, Any] = field(default_factory=dict)
    last_updated: str = field(default_factory=lambda: datetime.now().date().isoformat())


def ensure_storage() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _coerce_holding(value: Any) -> Holding:
    if isinstance(value, Holding):
        return value
    if isinstance(value, dict):
        return Holding(shares=float(value.get("shares", 0.0)), average_cost=value.get("average_cost"))
    return Holding(shares=float(value), average_cost=None)


def load_portfolio_state(path: str | Path = PORTFOLIO_STATE_PATH) -> PortfolioState:
    path = Path(path)
    if not path.exists():
        return PortfolioState(cash=0.0, holdings={}, settings={})
    raw = json.loads(path.read_text())
    holdings = {ticker: _coerce_holding(v) for ticker, v in raw.get("holdings", {}).items()}
    return PortfolioState(
        cash=float(raw.get("cash", 0.0)),
        holdings=holdings,
        strategy=raw.get("strategy", "Top-K Momentum"),
        settings=raw.get("settings", {}),
        last_updated=raw.get("last_updated", datetime.now().date().isoformat()),
    )


def save_portfolio_state(state: PortfolioState, path: str | Path = PORTFOLIO_STATE_PATH) -> None:
    ensure_storage()
    state.last_updated = datetime.now().date().isoformat()
    serializable = asdict(state)
    Path(path).write_text(json.dumps(serializable, indent=2))


def holdings_to_frame(state: PortfolioState) -> pd.DataFrame:
    rows = []
    for ticker, h in sorted(state.holdings.items()):
        if h.shares > 0:
            rows.append({"ticker": ticker, "shares": h.shares, "average_cost": h.average_cost})
    return pd.DataFrame(rows, columns=["ticker", "shares", "average_cost"])


def frame_to_holdings(df: pd.DataFrame, valid_tickers: set[str] | None = None) -> dict[str, Holding]:
    holdings: dict[str, Holding] = {}
    if df is None or df.empty:
        return holdings
    for _, row in df.iterrows():
        ticker = str(row.get("ticker", "")).upper().strip()
        if not ticker or ticker == "NAN":
            continue
        if valid_tickers is not None and ticker not in valid_tickers:
            continue
        shares = float(row.get("shares", 0.0) or 0.0)
        avg = row.get("average_cost", None)
        avg_cost = None if pd.isna(avg) or avg == "" else float(avg)
        if shares > 0:
            holdings[ticker] = Holding(shares=shares, average_cost=avg_cost)
    return holdings


def portfolio_value(state: PortfolioState, latest_prices: pd.Series) -> float:
    value = float(state.cash)
    for ticker, holding in state.holdings.items():
        if ticker in latest_prices:
            value += holding.shares * float(latest_prices[ticker])
    return value


def holdings_market_table(state: PortfolioState, latest_prices: pd.Series, target_weights: pd.Series | None = None) -> pd.DataFrame:
    total_value = portfolio_value(state, latest_prices)
    rows = []
    for ticker, holding in sorted(state.holdings.items()):
        price = float(latest_prices.get(ticker, 0.0))
        market_value = holding.shares * price
        current_weight = market_value / total_value if total_value > 0 else 0.0
        target_weight = float(target_weights.get(ticker, 0.0)) if target_weights is not None else 0.0
        unrealized_pnl = None
        if holding.average_cost is not None:
            unrealized_pnl = (price - holding.average_cost) * holding.shares
        rows.append({
            "ticker": ticker,
            "shares": holding.shares,
            "average_cost": holding.average_cost,
            "latest_price": price,
            "market_value": market_value,
            "current_weight": current_weight,
            "target_weight": target_weight,
            "weight_gap": target_weight - current_weight,
            "unrealized_pnl": unrealized_pnl,
        })
    return pd.DataFrame(rows)


def append_portfolio_snapshot(state: PortfolioState, latest_prices: pd.Series, path: str | Path = SNAPSHOT_LOG_PATH) -> None:
    ensure_storage()
    today = datetime.now().date().isoformat()
    row = {
        "date": today,
        "cash": state.cash,
        "portfolio_value": portfolio_value(state, latest_prices),
        "strategy": state.strategy,
        "last_updated": state.last_updated,
    }
    p = Path(path)
    df = pd.DataFrame([row])
    if p.exists():
        old = pd.read_csv(p)
        old = old[old["date"] != today]
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(p, index=False)
