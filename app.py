from __future__ import annotations

import streamlit as st

from src.data_loader import load_price_matrix, latest_prices
from src.portfolio_state import load_portfolio_state, portfolio_value, append_portfolio_snapshot
from src.paths import NASDAQ_PRICES_PATH
from src.market_data import load_data_metadata
from src.privacy import private_storage_summary
from src.recommendation_ui import render_recommendation_dashboard

st.set_page_config(page_title="NASDAQ-100 Portfolio App", page_icon="📈", layout="wide")

st.title("NASDAQ-100 Personal Portfolio Strategy App")
st.caption("Educational research app for target-weight strategies, recommendation tracking, and portfolio monitoring.")

st.warning("This app is for educational and personal research use only. It does not provide financial advice.")

privacy = private_storage_summary()
st.info(
    "Privacy mode: portfolio setup, recommendations, execution logs, and snapshots are stored only in "
    f"`{privacy['storage_dir']}` on this machine. The repo ignores `storage/*.json`, "
    "`storage/*.csv`, local databases, `.env`, and `.streamlit/secrets.toml`."
)

@st.cache_data(show_spinner=False)
def cached_prices():
    return load_price_matrix(NASDAQ_PRICES_PATH)

prices = cached_prices()
metadata = load_data_metadata()
state = load_portfolio_state()
latest = latest_prices(prices)
value = portfolio_value(state, latest)
setup_done = bool(state.holdings) or float(state.cash or 0.0) > 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Cash", f"${state.cash:,.2f}")
col2.metric("Portfolio Value", f"${value:,.2f}")
col3.metric("Holdings", len(state.holdings))
col4.metric("Latest Data Date", prices.index[-1].date().isoformat() if not prices.empty else "N/A")

if metadata:
    st.caption(f"Market data source: {metadata.get('source', 'local CSV')} | Last refresh UTC: {metadata.get('refreshed_at_utc', 'N/A')}")
else:
    st.caption("Market data source: bundled local CSV. Open Data Update to download the latest NASDAQ-100 prices.")

if setup_done:
    st.divider()
    st.header("Today’s Strategy Recommendation")
    render_recommendation_dashboard(prices, key_prefix="home", show_full_table=False)

    with st.expander("Portfolio workflow and maintenance", expanded=False):
        st.markdown(
            """
1. Use **Initial Setup** only when cash, holdings, strategy parameters, or trading preferences need to change.
2. The home page opens directly to **Strategy Recommendation** after setup is complete.
3. Use **Data Update** whenever you want the latest NASDAQ-100, NDX, or supplemental ticker prices.
4. Use **Portfolio Tracker** and **Action History** to monitor current state and past actions.
5. Use **Backtest Lab** to test strategies before selecting them for tracking.
            """
        )
        if st.button("Save today’s portfolio snapshot"):
            append_portfolio_snapshot(load_portfolio_state(), latest)
            st.success("Snapshot saved.")
else:
    st.subheader("Setup required")
    st.write("Open **Initial Setup** to enter cash, holdings, strategy, and trading preferences. After that, this home page will show your daily strategy recommendations first.")
    st.markdown(
        """
### Workflow
1. Open **Initial Setup** and enter cash, holdings, strategy, and trading preferences.
2. Return to this home page to see daily strategy recommendations at the top.
3. Mark whether recommendations were executed. No input means not executed.
4. Use **Portfolio Tracker** and **Action History** to monitor current state and past actions.
5. Open **Data Update** whenever you want to download the latest market data.
        """
    )
