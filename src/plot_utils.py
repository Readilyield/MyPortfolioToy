"""Plotting helper functions for Course Project 1."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd



def plot_nav_curves(result_dict: dict, title: str = "Strategy NAV Comparison"):
    """Plot NAV curves from multiple backtest results."""
    plt.figure(figsize=(10, 6))
    for name, result in result_dict.items():
            plt.plot(result.nav.index, result.nav.values, label=name)
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("NAV")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_nav_and_NDX(result_dict: dict, ndx_path: str, 
                     title: str = "Strategy NAV with NDX"):
    """Plot NAV curves from multiple backtest results and NDX real data"""
    # Convert nav series into a dataframe with date column
    first = True


    # Load NDX history
    ndx_df = pd.read_csv(ndx_path)
    ndx_df["Date"] = pd.to_datetime(ndx_df["Date"])
    ndx_df = ndx_df.rename(columns={"Date": "date", "Close/Last": "close"})
    ndx_df = ndx_df.sort_values("date").reset_index(drop=True)
    ndx_df["norm"] = ndx_df["close"] / ndx_df["close"].iloc[0]
    
    plt.figure(figsize=(10, 6))
    
    for name, result in result_dict.items():
        nav_df = result.nav.reset_index()
        nav_df.columns = ["date", "nav"]
        nav_df["date"] = pd.to_datetime(nav_df["date"])
        plot_df = pd.merge(nav_df, ndx_df, on="date", how="inner").sort_values("date")
        if first:
            plt.plot(plot_df["date"], plot_df["norm"], label="NDX",color="pink")
            first = False
        plt.plot(plot_df["date"], plot_df["nav"], label=name, alpha=0.7)
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("NAV")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_drawdown(nav: pd.Series, title: str = "Drawdown"):
    """Plot drawdown of a single strategy."""
    running_max = nav.cummax()
    drawdown = nav / running_max - 1.0

    plt.figure(figsize=(10, 4))
    plt.plot(drawdown.index, drawdown.values)
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.grid(True)
    plt.tight_layout()
    plt.show()



def plot_weights_over_time(weights: pd.DataFrame, tickers: list[str] | None = None, title: str = "Portfolio Weights"):
    """Plot selected portfolio weights through time."""
    plot_df = weights.copy()
    if tickers is not None:
        plot_df = plot_df[tickers]

    plt.figure(figsize=(10, 6))
    for col in plot_df.columns:
        plt.plot(plot_df.index, plot_df[col], label=col)
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Weight")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()



def plot_mean_nav_with_band(mean_nav: pd.Series, nav_paths: pd.DataFrame, title: str = "Mean NAV Across Simulations"):
    """Plot mean NAV with a one-standard-deviation band across simulations."""
    std_nav = nav_paths.std(axis=1, ddof=0)
    lower = mean_nav - std_nav
    upper = mean_nav + std_nav

    plt.figure(figsize=(10, 6))
    plt.plot(mean_nav.index, mean_nav.values, label="Mean NAV")
    plt.fill_between(mean_nav.index, lower.values, upper.values, alpha=0.2, label="Mean ± 1 std")
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("NAV")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()



def plot_metric_summary(metric_summary: pd.DataFrame, title: str = "Simulation Metric Summary"):
    """Plot the mean value of each metric with one-standard-deviation error bars."""
    plot_df = metric_summary.copy()
    plt.figure(figsize=(10, 5))
    plt.bar(plot_df.index, plot_df["mean"].values, yerr=plot_df["std"].values, capsize=4)
    plt.title(title)
    plt.ylabel("Metric value")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()



def plot_strategy_with_NDX_and_ma(results: dict, strategy_name: str, ndx_path: str,
                                 ma_short: int=10, ma_long: int=50):
    """
    Plot a strategy's nav curve with normalized value of NDX, and
    short ma and long ma of the market (using NDX data)
    """
    # Get BacktestResult object
    result = results[strategy_name]

    # Convert nav series into a dataframe with date column
    nav_df = result.nav.reset_index()
    nav_df.columns = ["date", "nav"]
    nav_df["date"] = pd.to_datetime(nav_df["date"])

    # Load NDX history
    ndx_df = pd.read_csv(ndx_path)
    ndx_df["Date"] = pd.to_datetime(ndx_df["Date"])
    ndx_df = ndx_df.rename(columns={"Date": "date", "Close/Last": "close"})
    ndx_df = ndx_df.sort_values("date").reset_index(drop=True)

    # Build moving averages for the market
    ndx_df["market_short_ma"] = ndx_df["close"].rolling(ma_short).mean()
    ndx_df["market_long_ma"] = ndx_df["close"].rolling(ma_long).mean()

    # Merge strategy NAV with NDX data
    plot_df = nav_df.merge(
        ndx_df[["date", "close", "market_short_ma", "market_long_ma"]],
        on="date",
        how="inner"
    )

    # Normalize series so they can be shown on one chart
    plot_df["nav_norm"] = plot_df["nav"] / plot_df["nav"].iloc[0]
    plot_df["ndx_norm"] = plot_df["close"] / plot_df["close"].iloc[0]
    plot_df["short_ma_norm"] = plot_df["market_short_ma"] / plot_df["close"].iloc[0]
    plot_df["long_ma_norm"] = plot_df["market_long_ma"] / plot_df["close"].iloc[0]

    plt.figure(figsize=(13, 7))
    plt.plot(plot_df["date"], plot_df["ndx_norm"], label="NDX",color="pink")
    plt.plot(plot_df["date"], plot_df["short_ma_norm"], label="Market Short MA (20)",color="orange")
    plt.plot(plot_df["date"], plot_df["long_ma_norm"], label="Market Long MA (200)")

    if strategy_name == "Trend TopK Momentum":
        plt.plot(plot_df["date"], plot_df["nav_norm"], label="Trend TopK Momentum (A1)",color="green")
    else:
        plt.plot(plot_df["date"], plot_df["nav_norm"], label=f"{strategy_name}",color="green")

    plt.title("Trend TopK Momentum vs NDX and Market Moving Averages",fontsize=16)
    plt.xlabel("Date",fontsize=12)
    plt.ylabel("Normalized Value",fontsize=12)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    
