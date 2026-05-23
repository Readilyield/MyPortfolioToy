from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def plot_current_vs_target(table: pd.DataFrame):
    if table.empty:
        return None
    df = table[["ticker", "current_weight", "target_weight"]].melt("ticker", var_name="weight_type", value_name="weight")
    return px.bar(df, x="ticker", y="weight", color="weight_type", barmode="group", title="Current vs Target Weights")


def plot_nav_vs_benchmark(nav: pd.Series, benchmark: pd.Series | None = None):
    fig = go.Figure()
    if nav is not None and not nav.empty:
        fig.add_trace(go.Scatter(x=nav.index, y=nav / nav.iloc[0], mode="lines", name="Strategy NAV"))
    if benchmark is not None and not benchmark.empty:
        b = benchmark.dropna()
        fig.add_trace(go.Scatter(x=b.index, y=b / b.iloc[0], mode="lines", name="NDX"))
    fig.update_layout(title="Normalized NAV vs NDX", xaxis_title="Date", yaxis_title="Normalized Value")
    return fig


def plot_portfolio_value(snapshot_df: pd.DataFrame):
    if snapshot_df.empty or "portfolio_value" not in snapshot_df:
        return None
    df = snapshot_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    return px.line(df, x="date", y="portfolio_value", title="Tracked Portfolio Value")
