from __future__ import annotations

import streamlit as st

from src.data_loader import load_price_matrix
from src.paths import NASDAQ_PRICES_PATH
from src.recommendation_ui import render_recommendation_dashboard

st.set_page_config(page_title="Strategy Recommendation", layout="wide")
st.title("Strategy Recommendation")
st.caption("Generate daily NASDAQ-100 strategy actions and record executions.")

@st.cache_data(show_spinner=False)
def cached_prices():
    return load_price_matrix(NASDAQ_PRICES_PATH)

prices = cached_prices()
render_recommendation_dashboard(prices, key_prefix="recommendation_page", show_full_table=True)
