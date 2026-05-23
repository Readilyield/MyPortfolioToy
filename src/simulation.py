"""Simulation utilities for Course Project 1.

This module creates synthetic stock price paths using simple normal-based models.
The goal is not to build a production-quality market simulator. Instead, the goal
is to give students a readable way to stress-test strategies on alternative data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd


@dataclass
class SimulationSummary:
    """Store the simulated price paths and the model parameters used."""

    simulated_paths: List[pd.DataFrame]
    model_name: str
    parameters: dict



def _clean_returns(price_matrix: pd.DataFrame) -> pd.DataFrame:
    """Compute daily returns and remove the first NaN row."""
    returns = price_matrix.pct_change(fill_method=None)
    returns = returns.replace([np.inf, -np.inf], np.nan).dropna(how="all")
    return returns.fillna(0.0)



def simulate_independent_normal_prices(
    real_price_matrix: pd.DataFrame,
    n_simulations: int = 100,
    seed: Optional[int] = None,
) -> SimulationSummary:
    """Simulate prices from independent normal daily returns.
    Simple model:

    - estimate each stock's historical daily mean return
    - estimate each stock's historical daily variance
    - assume zero cross-stock correlation
    - simulate returns independently across stocks and time
    - rebuild price paths from the first observed real price

    """

    prices = real_price_matrix.sort_index().copy()
    returns = _clean_returns(prices)
    tickers = list(prices.columns)
    dates = prices.index
    
    mu = returns.mean(axis=0)
    var = returns.var(axis=0, ddof=0).clip(lower=1e-8)
    sigma = np.sqrt(var)
    rng = np.random.default_rng(seed)

    simulated_paths: List[pd.DataFrame] = []
    initial_prices = prices.iloc[0].clip(lower=0.01)

    for sim_id in range(n_simulations):
        sim_returns = pd.DataFrame(
            rng.normal(loc=mu.values, scale=sigma.values, size=(len(dates) - 1, len(tickers))),
            index=dates[1:],
            columns=tickers,
        )
        # Prevent impossible one-day collapses or explosions
        sim_returns = sim_returns.clip(lower=-0.95, upper=0.95)
        sim_prices = pd.DataFrame(index=dates, columns=tickers, dtype=float)
        sim_prices.iloc[0] = initial_prices.values
        for i in range(1, len(dates)):
            sim_prices.iloc[i] = sim_prices.iloc[i - 1].values * (1.0 + sim_returns.iloc[i - 1].values)
        sim_prices = sim_prices.clip(lower=0.01)
        simulated_paths.append(sim_prices)

    return SimulationSummary(
        simulated_paths=simulated_paths,
        model_name="independent_normal_returns",
        parameters={
            "mean_daily_return": mu,
            "daily_variance": var,
        },)



def simulate_factor_normal_prices(
    real_price_matrix: pd.DataFrame,
    n_simulations: int = 100,
    seed: Optional[int] = None,
    ) -> SimulationSummary:
    """Simulate prices from a simple one-factor normal return model.

    Model idea:
    - Estimate daily stock returns from real data.
    - Estimate a market return series as the equal-weight average stock return.
    - For each stock i, fit a simple linear relation
          r_i = alpha_i + beta_i * r_market + epsilon_i.
    - Simulate a normal market shock and a normal idiosyncratic shock each day.
    - Convert simulated returns back into price paths.

    This model is still based on normal draws, but it preserves two useful facts:
    - stocks can move together through the market factor;
    - each stock keeps its own drift, beta, and residual volatility.
    """
    prices = real_price_matrix.sort_index().copy()
    returns = _clean_returns(prices)
    tickers = list(prices.columns)
    dates = prices.index

    market_returns = returns.mean(axis=1)
    market_mean = float(market_returns.mean())
    market_std = float(market_returns.std(ddof=0))
    if market_std <= 1e-8:
        market_std = 1e-8

    alphas = pd.Series(index=tickers, dtype=float)
    betas = pd.Series(index=tickers, dtype=float)
    residual_stds = pd.Series(index=tickers, dtype=float)

    market_centered = market_returns - market_mean
    market_var = float((market_centered.pow(2)).mean())
    market_var = max(market_var, 1e-8)

    for ticker in tickers:
        y = returns[ticker].fillna(0.0)
        y_mean = float(y.mean())
        cov_im = float(((y - y_mean) * (market_returns - market_mean)).mean())
        beta = cov_im / market_var
        alpha = y_mean - beta * market_mean
        fitted = alpha + beta * market_returns
        residual = y - fitted
        residual_std = float(residual.std(ddof=0))

        alphas[ticker] = alpha
        betas[ticker] = beta
        residual_stds[ticker] = max(residual_std, 1e-8)

    rng = np.random.default_rng(seed)
    simulated_paths: List[pd.DataFrame] = []
    initial_prices = prices.iloc[0].clip(lower=0.01)

    for sim_id in range(n_simulations):
        sim_returns = pd.DataFrame(index=dates[1:], columns=tickers, dtype=float)
        for current_date in dates[1:]:
            market_shock = rng.normal(loc=market_mean, scale=market_std)
            idio_shocks = rng.normal(loc=0.0, scale=residual_stds.values, size=len(tickers))
            day_returns = alphas.values + betas.values * market_shock + idio_shocks
            # Avoid impossible price explosions or crashes in a teaching example.
            day_returns = np.clip(day_returns, -0.95, 0.95)
            sim_returns.loc[current_date] = day_returns

        sim_prices = pd.DataFrame(index=dates, columns=tickers, dtype=float)
        sim_prices.iloc[0] = initial_prices.values
        for i in range(1, len(dates)):
            prev_prices = sim_prices.iloc[i - 1].values
            day_returns = sim_returns.iloc[i - 1].values
            sim_prices.iloc[i] = prev_prices * (1.0 + day_returns)
        sim_prices = sim_prices.clip(lower=0.01)
        simulated_paths.append(sim_prices)

    return SimulationSummary(
        simulated_paths=simulated_paths,
        model_name="factor_normal_returns",
        parameters={
            "alphas": alphas,
            "betas": betas,
            "residual_stds": residual_stds,
            "market_mean": market_mean,
            "market_std": market_std,
        },
    )
