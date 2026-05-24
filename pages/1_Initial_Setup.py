from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_loader import load_ticker_universe, normalize_ticker
from src.portfolio_state import (
    PortfolioState,
    Holding,
    holdings_to_frame,
    frame_to_holdings,
    load_portfolio_state,
    save_portfolio_state,
)
from src.strategy_registry import STRATEGY_FACTORIES, DEFAULT_STRATEGY_PARAMS

st.set_page_config(page_title="Initial Setup", layout="wide")
st.title("Initial Setup")

nasdaq_universe = load_ticker_universe()
nasdaq_set = set(nasdaq_universe)
state = load_portfolio_state()

st.info(
    "You may enter any ticker or ETF in your holdings table, such as DUOL, LULU, or IGV. "
    "The strategy recommendation engine will still only generate buy/sell recommendations from the NASDAQ-100 universe. "
    "Non-NASDAQ-100 tickers are tracked passively in the portfolio dashboard once you refresh supplemental prices."
)

st.subheader("Cash and Existing Holdings")
cash = st.number_input("Cash amount", min_value=0.0, value=float(state.cash), step=100.0, format="%.2f")

existing = holdings_to_frame(state)
if existing.empty:
    existing = pd.DataFrame([{"ticker": "AAPL", "shares": 0.0, "average_cost": None}], columns=["ticker", "shares", "average_cost"])

edited = st.data_editor(
    existing,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "ticker": st.column_config.TextColumn(
            "Ticker",
            help="Any Yahoo-compatible stock or ETF ticker. Examples: AAPL, DUOL, LULU, IGV, BRK-B.",
            required=True,
        ),
        "shares": st.column_config.NumberColumn("Shares", min_value=0.0, step=1.0, format="%.6f"),
        "average_cost": st.column_config.NumberColumn("Average Cost", min_value=0.0, step=0.01, format="%.4f"),
    },
)

quick_tickers = st.text_input(
    "Quick add tickers, optional",
    placeholder="Example: DUOL, LULU, IGV",
    help="Comma- or space-separated tickers to add with zero shares. Fill shares and average cost after they appear in the table, then save again.",
)

st.subheader("Strategy")
strategy_names = list(STRATEGY_FACTORIES.keys())
strategy = st.selectbox("Portfolio strategy", strategy_names, index=strategy_names.index(state.strategy) if state.strategy in strategy_names else 0)

params = DEFAULT_STRATEGY_PARAMS.get(strategy, {}).copy()
st.write("Strategy parameters")
param_cols = st.columns(min(4, max(1, len(params))))
new_params = {}
for i, (k, v) in enumerate(params.items()):
    with param_cols[i % len(param_cols)]:
        if isinstance(v, int):
            new_params[k] = st.number_input(k, min_value=1, value=int(state.settings.get("strategy_params", {}).get(k, v)), step=1)
        else:
            new_params[k] = st.number_input(k, value=float(state.settings.get("strategy_params", {}).get(k, v)))

st.subheader("Trading Settings")
col1, col2, col3 = st.columns(3)
with col1:
    max_alloc = st.number_input("Max allocation per stock", min_value=0.01, max_value=1.0, value=float(state.settings.get("max_allocation_per_stock", 0.20)), step=0.01)
with col2:
    min_trade = st.number_input("Minimum trade value", min_value=0.0, value=float(state.settings.get("min_trade_value", 50.0)), step=10.0)
with col3:
    price_band = st.number_input("Minimum price band %", min_value=0.0, max_value=0.20, value=float(state.settings.get("minimum_price_band_pct", 0.01)), step=0.005, format="%.3f")

if st.button("Save setup", type="primary"):
    holdings = frame_to_holdings(edited, valid_tickers=None)

    if quick_tickers.strip():
        for token in quick_tickers.replace(",", " ").split():
            ticker = normalize_ticker(token)
            if ticker and ticker not in holdings:
                holdings[ticker] = Holding(shares=0.0, average_cost=None)

    # Keep parameters separated by strategy. This prevents arguments from one
    # strategy, such as short_lookback from Momentum with Pullback, from being
    # passed into another strategy constructor such as Top-K Momentum.
    previous_settings = state.settings or {}
    params_by_strategy = dict(previous_settings.get("strategy_params_by_strategy", {}) or {})
    if state.strategy and previous_settings.get("strategy_params") and state.strategy not in params_by_strategy:
        params_by_strategy[state.strategy] = previous_settings.get("strategy_params", {})
    params_by_strategy[strategy] = new_params

    new_state = PortfolioState(
        cash=float(cash),
        holdings=holdings,
        strategy=strategy,
        settings={
            "strategy_params": new_params,
            "strategy_params_by_strategy": params_by_strategy,
            "max_allocation_per_stock": float(max_alloc),
            "min_trade_value": float(min_trade),
            "minimum_price_band_pct": float(price_band),
        },
    )
    save_portfolio_state(new_state)
    outside = sorted(t for t in holdings if t not in nasdaq_set)
    st.success(f"Portfolio setup saved for strategy: {strategy}.")
    if len(params_by_strategy) > 1:
        st.caption("Configured strategies: " + ", ".join(sorted(params_by_strategy)))
    if outside:
        st.warning(
            "These holdings are outside the NASDAQ-100 strategy universe and will be tracked passively: "
            + ", ".join(outside)
            + ". Go to Data Update and refresh tracked supplemental tickers to download their prices."
        )
