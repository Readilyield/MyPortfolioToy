from __future__ import annotations
import numpy as np
import pandas as pd


def compute_nav_metrics(nav: pd.Series) -> pd.Series:
    nav = nav.dropna()
    if nav.empty:
        return pd.Series(dtype=float)
    returns = nav.pct_change(fill_method=None).fillna(0.0)
    cumulative_return = nav.iloc[-1] / nav.iloc[0] - 1.0 if nav.iloc[0] else 0.0
    annualized_return = (1 + returns.mean()) ** 252 - 1
    annualized_volatility = returns.std(ddof=0) * np.sqrt(252)
    sharpe = annualized_return / annualized_volatility if annualized_volatility > 0 else 0.0
    drawdown = nav / nav.cummax() - 1
    return pd.Series({
        "cumulative_return": cumulative_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe,
        "max_drawdown": drawdown.min(),
    })
