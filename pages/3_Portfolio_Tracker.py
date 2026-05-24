from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_loader import load_price_matrix, load_tracking_price_matrix, latest_prices, load_ndx_series, load_ticker_universe
from src.portfolio_state import load_portfolio_state, portfolio_value, holdings_market_table
from src.recommendation_engine import compute_target_weights
from src.plotting import plot_current_vs_target, plot_portfolio_value
from src.paths import NASDAQ_PRICES_PATH, NDX_PRICES_PATH, SNAPSHOT_LOG_PATH

st.set_page_config(page_title="Portfolio Tracker", layout="wide")
st.title("Portfolio Tracker")

@st.cache_data(show_spinner=False)
def cached_prices(holding_tickers: tuple[str, ...]):
    return load_tracking_price_matrix(set(holding_tickers))

state = load_portfolio_state()
prices = cached_prices(tuple(sorted(state.holdings.keys())))
latest = latest_prices(prices)
settings = state.settings or {}
strategy_prices = load_price_matrix(NASDAQ_PRICES_PATH)
target_weights = compute_target_weights(
    strategy_prices,
    state.strategy,
    settings.get("strategy_params", {}),
    float(settings.get("max_allocation_per_stock", 0.20)),
)
value = portfolio_value(state, latest)

c1, c2, c3 = st.columns(3)
c1.metric("Cash", f"${state.cash:,.2f}")
c2.metric("Total Portfolio Value", f"${value:,.2f}")
c3.metric("Latest Data Date", prices.index[-1].date().isoformat())

nasdaq_set = set(load_ticker_universe())
outside = sorted(t for t in state.holdings if t not in nasdaq_set)
if outside:
    st.info("Tracking passive non-NASDAQ-100 holdings: " + ", ".join(outside) + ". These are included in portfolio value when supplemental prices are available, but they are not part of buy/sell recommendations.")

table = holdings_market_table(state, latest, target_weights)
st.subheader("Current Holdings")
if table.empty:
    st.info("No holdings saved yet. Go to Initial Setup first.")
else:
    st.dataframe(table, use_container_width=True)
    missing = table[(table["latest_price"].isna()) | (table["latest_price"] <= 0)]["ticker"].tolist() if "latest_price" in table.columns else []
    if missing:
        st.warning("Missing latest prices for: " + ", ".join(missing) + ". Go to Data Update and refresh tracked supplemental tickers.")
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
