from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_loader import load_price_matrix, latest_prices, load_ndx_series
from src.portfolio_state import load_portfolio_state, portfolio_value, holdings_market_table
from src.recommendation_engine import compute_target_weights
from src.plotting import plot_current_vs_target, plot_portfolio_value
from src.paths import NASDAQ_PRICES_PATH, NDX_PRICES_PATH, SNAPSHOT_LOG_PATH

st.set_page_config(page_title="Portfolio Tracker", layout="wide")
st.title("Portfolio Tracker")

@st.cache_data(show_spinner=False)
def cached_prices():
    return load_price_matrix(NASDAQ_PRICES_PATH)

prices = cached_prices()
latest = latest_prices(prices)
state = load_portfolio_state()
settings = state.settings or {}
target_weights = compute_target_weights(
    prices,
    state.strategy,
    settings.get("strategy_params", {}),
    float(settings.get("max_allocation_per_stock", 0.20)),
)
value = portfolio_value(state, latest)

c1, c2, c3 = st.columns(3)
c1.metric("Cash", f"${state.cash:,.2f}")
c2.metric("Total Portfolio Value", f"${value:,.2f}")
c3.metric("Latest Data Date", prices.index[-1].date().isoformat())

table = holdings_market_table(state, latest, target_weights)
st.subheader("Current Holdings")
if table.empty:
    st.info("No holdings saved yet. Go to Initial Setup first.")
else:
    st.dataframe(table, use_container_width=True)
    fig = plot_current_vs_target(table)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)

st.subheader("Portfolio Snapshot History")
try:
    snapshots = pd.read_csv(SNAPSHOT_LOG_PATH)
except FileNotFoundError:
    snapshots = pd.DataFrame()
fig = plot_portfolio_value(snapshots)
if fig is not None:
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No saved snapshots yet. Save one from the home page.")

st.subheader("Benchmark")
try:
    ndx = load_ndx_series(NDX_PRICES_PATH)
    st.line_chart((ndx / ndx.iloc[0]).rename("Normalized NDX"))
except Exception as exc:
    st.warning(f"Could not load NDX benchmark: {exc}")
