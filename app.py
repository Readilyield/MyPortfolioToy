from __future__ import annotations

import streamlit as st

from src.data_loader import load_price_matrix, latest_prices
from src.portfolio_state import load_portfolio_state, portfolio_value, append_portfolio_snapshot
from src.paths import NASDAQ_PRICES_PATH

st.set_page_config(page_title="NASDAQ-100 Portfolio App", page_icon="📈", layout="wide")

st.title("NASDAQ-100 Personal Portfolio Strategy App")
st.caption("Educational research app for target-weight strategies, recommendation tracking, and portfolio monitoring.")

st.warning("This app is for educational and personal research use only. It does not provide financial advice.")

@st.cache_data(show_spinner=False)
def cached_prices():
    return load_price_matrix(NASDAQ_PRICES_PATH)

prices = cached_prices()
state = load_portfolio_state()
latest = latest_prices(prices)
value = portfolio_value(state, latest)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Cash", f"${state.cash:,.2f}")
col2.metric("Portfolio Value", f"${value:,.2f}")
col3.metric("Holdings", len(state.holdings))
col4.metric("Latest Data Date", prices.index[-1].date().isoformat() if not prices.empty else "N/A")

st.subheader("Current Strategy")
st.write(state.strategy)

if st.button("Save today’s portfolio snapshot"):
    append_portfolio_snapshot(state, latest)
    st.success("Snapshot saved.")

st.subheader("Workflow")
st.markdown(
    """
1. Open **Initial Setup** and enter cash, holdings, strategy, and trading preferences.
2. Open **Strategy Recommendation** to generate daily buy/sell/hold actions.
3. Mark whether recommendations were executed. No input means not executed.
4. Use **Portfolio Tracker** and **Action History** to monitor current state and past actions.
5. Use **Backtest Lab** to test strategies before selecting them for tracking.
    """
)
