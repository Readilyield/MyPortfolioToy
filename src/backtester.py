"""Core backtesting engine for Course Project 1.

The engine is intentionally simple:
- strategies observe close prices up to day t
- trades happen at day t close
- portfolio return is earned from day t close to day t+1 close
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from src.utils import compute_daily_returns, normalize_weights


StrategyFunction = Callable[[pd.DataFrame, pd.Timestamp], pd.Series]


@dataclass
class BacktestResult:
    nav: pd.Series
    daily_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    metrics: pd.Series


@dataclass
class SimulationExperimentResult:
    strategy_name: str
    mode: str
    simulation_model: str
    nav_paths: pd.DataFrame
    mean_nav: pd.Series
    metric_table: pd.DataFrame
    metric_summary: pd.DataFrame


class Backtester:
    """A reusable daily-close backtester."""

    def __init__(
        self,
        price_matrix: pd.DataFrame,
        initial_cash: float = 1.0,
        transaction_cost: float = 0.0,
    ) -> None:
        self.real_prices = price_matrix.sort_index().copy()
        self.simulated_prices: Optional[pd.DataFrame] = None
        self.use_simulated_data: bool = False
        self.prices = self.real_prices.copy()
        self.returns = compute_daily_returns(self.prices)
        self.initial_cash = initial_cash
        self.transaction_cost = transaction_cost


    def set_price_data(self, price_matrix: pd.DataFrame) -> None:
        """Replace the active price matrix and recompute returns."""
        self.prices = price_matrix.sort_index().copy()
        self.returns = compute_daily_returns(self.prices)

    def set_simulated_data(self, simulated_price_matrix: pd.DataFrame) -> None:
        """Store one simulated dataset that can be activated with a toggle."""
        self.simulated_prices = simulated_price_matrix.sort_index().copy()

    def set_data_mode(self, use_simulated: bool = False) -> None:
        """Toggle between real data and simulated data."""
        self.use_simulated_data = use_simulated
        if use_simulated and self.simulated_prices is not None:
            self.set_price_data(self.simulated_prices)
        else:
            self.set_price_data(self.real_prices)

    def run_strategy(
        self,
        strategy_func: StrategyFunction,
        strategy_name: str = "strategy",
        start_date: Optional[str] = None,
    ) -> BacktestResult:
        """Run a strategy that outputs target weights for each trading day.

        Parameters
        ----------
        strategy_func:
            Function with signature (price_history, current_date) -> pd.Series.
            The returned series should be indexed by ticker.
        start_date:
            Optional. Backtest starts from this date. Useful when a strategy
            needs a warm-up window such as 20 or 50 days.
        """
        dates = list(self.prices.index)
        tickers = list(self.prices.columns)

        weights_table = pd.DataFrame(0.0, index=dates, columns=tickers)
        turnover = pd.Series(0.0, index=dates, name="turnover")
        strategy_returns = pd.Series(0.0, index=dates, name=strategy_name)
        nav = pd.Series(index=dates, dtype=float, name="nav")

        current_weights = pd.Series(0.0, index=tickers)
        nav.iloc[0] = self.initial_cash

        # Choose the first date that can be traded.
        if start_date is not None:
            start_date = pd.Timestamp(start_date)

        for i, current_date in enumerate(dates[:-1]):
            if start_date is not None and current_date < start_date:
                weights_table.loc[current_date] = current_weights
                nav.iloc[i + 1] = nav.iloc[i]
                continue

            # History available to the strategy includes today's close.
            history = self.prices.loc[:current_date].copy()
            target_weights = strategy_func(history, current_date)
            target_weights = target_weights.reindex(tickers).fillna(0.0)
            target_weights = normalize_weights(target_weights)

            # Trading cost depends on how much the portfolio weights change.
            day_turnover = np.abs(target_weights - current_weights).sum()
            turnover.loc[current_date] = day_turnover
            cost = self.transaction_cost * day_turnover

            # The chosen target weights are held from today's close to next day's close.
            next_date = dates[i + 1]
            next_day_returns = self.returns.loc[next_date].fillna(0.0)
            gross_return = float((target_weights * next_day_returns).sum())
            net_return = gross_return - cost

            strategy_returns.loc[next_date] = net_return
            nav.iloc[i + 1] = nav.iloc[i] * (1.0 + net_return)
            weights_table.loc[current_date] = target_weights
            current_weights = target_weights

        # Save the final known weights on the last date.
        weights_table.loc[dates[-1]] = current_weights
        metrics = self.compute_metrics(strategy_returns, nav)
        return BacktestResult(
            nav=nav,
            daily_returns=strategy_returns,
            weights=weights_table,
            turnover=turnover,
            metrics=metrics,
        )

    @staticmethod
    def compute_metrics(daily_returns: pd.Series, nav: pd.Series) -> pd.Series:
        """Compute common performance metrics for a backtest."""
        r = daily_returns.fillna(0.0)
        total_return = nav.iloc[-1] / nav.iloc[0] - 1.0
        annualized_return = (1.0 + r.mean()) ** 252 - 1.0
        annualized_volatility = r.std(ddof=0) * np.sqrt(252)
        sharpe_ratio = 0.0
        if annualized_volatility > 0:
            sharpe_ratio = annualized_return / annualized_volatility

        running_max = nav.cummax()
        drawdown = nav / running_max - 1.0
        max_drawdown = drawdown.min()
        win_rate = (r > 0).mean()

        downside_std = r[r < 0].std(ddof=0) * np.sqrt(252)
        sortino_ratio = 0.0
        if downside_std > 0:
            sortino_ratio = annualized_return / downside_std

        turnover_mean = 0.0
        if len(nav.index) > 1:
            turnover_like = nav.index  # placeholder to keep metric block simple

        return pd.Series(
            {
                "cumulative_return": total_return,
                "annualized_return": annualized_return,
                "annualized_volatility": annualized_volatility,
                "sharpe_ratio": sharpe_ratio,
                "sortino_ratio": sortino_ratio,
                "max_drawdown": max_drawdown,
                "win_rate": win_rate,
            }
        )

    def run_strategy_on_simulations(
        self,
        strategy_func: StrategyFunction,
        simulation_paths: List[pd.DataFrame],
        strategy_name: str = "strategy",
        simulation_model: str = "simulated",
        start_date: Optional[str] = None,
    ) -> SimulationExperimentResult:
        """Run the same strategy across many simulated price paths.

        The output is aggregated so the notebook can easily inspect:
        - the mean NAV curve across simulations;
        - the full table of metrics for each simulation;
        - the mean and variance of each metric.
        """
        nav_dict = {}
        metrics_rows = []

        original_real_prices = self.real_prices.copy()
        original_simulated_prices = None if self.simulated_prices is None else self.simulated_prices.copy()
        original_mode = self.use_simulated_data
        original_prices = self.prices.copy()

        for sim_id, sim_prices in enumerate(simulation_paths):
            self.set_simulated_data(sim_prices)
            self.set_data_mode(use_simulated=True)
            result = self.run_strategy(strategy_func, f"{strategy_name}_sim_{sim_id}", start_date=start_date)
            nav_dict[f"simulation_{sim_id}"] = result.nav
            row = result.metrics.copy()
            row["simulation_id"] = sim_id
            metrics_rows.append(row)

        nav_paths = pd.DataFrame(nav_dict)
        mean_nav = nav_paths.mean(axis=1)
        metric_table = pd.DataFrame(metrics_rows).set_index("simulation_id")
        metric_summary = pd.DataFrame({
            "mean": metric_table.mean(axis=0),
            "variance": metric_table.var(axis=0, ddof=0),
            "std": metric_table.std(axis=0, ddof=0),
        })

        self.real_prices = original_real_prices
        self.simulated_prices = original_simulated_prices
        self.use_simulated_data = original_mode
        self.prices = original_prices
        self.returns = compute_daily_returns(self.prices)

        return SimulationExperimentResult(
            strategy_name=strategy_name,
            mode="simulated",
            simulation_model=simulation_model,
            nav_paths=nav_paths,
            mean_nav=mean_nav,
            metric_table=metric_table,
            metric_summary=metric_summary,
        )


def compare_backtests(result_dict: Dict[str, BacktestResult]) -> pd.DataFrame:
    """Combine multiple backtest metric summaries into one table."""
    rows = {}
    for name, result in result_dict.items():
        rows[name] = result.metrics
    return pd.DataFrame(rows).T.sort_values("sharpe_ratio", ascending=False)
