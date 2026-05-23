from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pandas as pd

from src.paths import EXECUTION_LOG_PATH, STORAGE_DIR
from src.portfolio_state import PortfolioState, Holding, save_portfolio_state


def load_execution_log(path: str | Path = EXECUTION_LOG_PATH) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


def validate_execution(state: PortfolioState, action: str, ticker: str, shares: float, price: float) -> tuple[bool, str]:
    if shares < 0:
        return False, "Executed shares cannot be negative."
    if price <= 0:
        return False, "Executed price must be positive."
    if action == "BUY" and shares * price > state.cash + 1e-9:
        return False, "Insufficient cash for this buy execution."
    if action == "SELL":
        held = state.holdings.get(ticker, Holding()).shares
        if shares > held + 1e-9:
            return False, "Cannot sell more shares than currently held."
    return True, "OK"


def apply_execution(
    state: PortfolioState,
    ticker: str,
    action: str,
    executed: bool,
    executed_shares: float,
    executed_price: float,
    notes: str = "",
    save_state: bool = True,
) -> dict:
    """Apply a user-confirmed execution to cash and holdings."""
    ticker = ticker.upper().strip()
    action = action.upper().strip()
    executed_shares = float(executed_shares or 0.0)
    executed_price = float(executed_price or 0.0)

    cash_change = 0.0
    if executed:
        ok, msg = validate_execution(state, action, ticker, executed_shares, executed_price)
        if not ok:
            raise ValueError(msg)
        if action == "BUY":
            cash_change = -executed_shares * executed_price
            state.cash += cash_change
            holding = state.holdings.get(ticker, Holding())
            old_value = (holding.average_cost or 0.0) * holding.shares
            new_value = executed_shares * executed_price
            new_shares = holding.shares + executed_shares
            avg_cost = (old_value + new_value) / new_shares if new_shares > 0 else None
            state.holdings[ticker] = Holding(shares=new_shares, average_cost=avg_cost)
        elif action == "SELL":
            cash_change = executed_shares * executed_price
            state.cash += cash_change
            holding = state.holdings.get(ticker, Holding())
            new_shares = max(0.0, holding.shares - executed_shares)
            if new_shares == 0:
                state.holdings.pop(ticker, None)
            else:
                state.holdings[ticker] = Holding(shares=new_shares, average_cost=holding.average_cost)

    if save_state:
        save_portfolio_state(state)

    return {
        "date": datetime.now().date().isoformat(),
        "ticker": ticker,
        "recommended_action": action,
        "executed": bool(executed),
        "executed_shares": executed_shares if executed else 0.0,
        "executed_price": executed_price if executed else 0.0,
        "cash_change": cash_change,
        "notes": notes,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


def append_execution_log(row: dict, path: str | Path = EXECUTION_LOG_PATH) -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    p = Path(path)
    df = pd.DataFrame([row])
    if p.exists():
        old = pd.read_csv(p)
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(p, index=False)
