from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_loader import load_price_matrix, load_ndx_series
from src.backtester import Backtester
from src.strategy_registry import STRATEGY_FACTORIES, DEFAULT_STRATEGY_PARAMS, build_strategy
from src.plotting import plot_nav_vs_benchmark
from src.paths import NASDAQ_PRICES_PATH, NDX_PRICES_PATH

st.set_page_config(page_title="Backtest Lab", layout="wide")
st.title("Backtest Lab")

@st.cache_data(show_spinner=False)
def cached_prices():
    return load_price_matrix(NASDAQ_PRICES_PATH)

prices = cached_prices()
strategy_names = list(STRATEGY_FACTORIES.keys())
strategy_name = st.selectbox("Strategy", strategy_names)
params = DEFAULT_STRATEGY_PARAMS.get(strategy_name, {}).copy()

st.subheader("Parameters")
new_params = {}
cols = st.columns(min(4, max(1, len(params))))
for i, (k, v) in enumerate(params.items()):
    with cols[i % len(cols)]:
        new_params[k] = st.number_input(k, min_value=1, value=int(v), step=1) if isinstance(v, int) else st.number_input(k, value=float(v))

c1, c2, c3 = st.columns(3)
with c1:
    initial_cash = st.number_input("Initial cash", min_value=1.0, value=1.0, step=1000.0, format="%.2f")
with c2:
    transaction_cost = st.number_input("Transaction cost per turnover unit", min_value=0.0, value=0.0, step=0.0005, format="%.4f")
with c3:
    start_date = st.date_input("Start date", value=prices.index[min(252, len(prices)-1)].date())

if st.button("Run backtest", type="primary"):
    strategy = build_strategy(strategy_name, new_params)
    backtester = Backtester(prices, initial_cash=initial_cash, transaction_cost=transaction_cost)
    result = backtester.run_strategy(strategy, strategy_name=strategy_name, start_date=str(start_date))
    st.subheader("Metrics")
    st.dataframe(result.metrics.to_frame("value"), use_container_width=True)
    try:
        ndx = load_ndx_series(NDX_PRICES_PATH)
    except Exception:
        ndx = None
    st.plotly_chart(plot_nav_vs_benchmark(result.nav, ndx), use_container_width=True)
    st.subheader("Latest Weights")
    latest_weights = result.weights.iloc[-1]
    latest_weights = latest_weights[latest_weights > 0].sort_values(ascending=False)
    st.dataframe(latest_weights.rename("weight").to_frame(), use_container_width=True)
