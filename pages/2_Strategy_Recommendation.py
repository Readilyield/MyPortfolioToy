from __future__ import annotations

import streamlit as st

from src.data_loader import load_price_matrix
from src.portfolio_state import load_portfolio_state
from src.recommendation_engine import generate_recommendations, save_daily_recommendations
from src.execution_engine import apply_execution, append_execution_log
from src.paths import NASDAQ_PRICES_PATH

st.set_page_config(page_title="Strategy Recommendation", layout="wide")
st.title("Strategy Recommendation")

@st.cache_data(show_spinner=False)
def cached_prices():
    return load_price_matrix(NASDAQ_PRICES_PATH)

state = load_portfolio_state()
prices = cached_prices()
settings = state.settings or {}

st.caption(f"Strategy: {state.strategy} | Latest data date: {prices.index[-1].date().isoformat()}")

if st.button("Generate / refresh recommendations", type="primary"):
    recs = generate_recommendations(
        state=state,
        price_history=prices,
        strategy_name=state.strategy,
        strategy_params=settings.get("strategy_params", {}),
        max_allocation_per_stock=float(settings.get("max_allocation_per_stock", 0.20)),
        min_trade_value=float(settings.get("min_trade_value", 50.0)),
        minimum_price_band_pct=float(settings.get("minimum_price_band_pct", 0.01)),
    )
    save_daily_recommendations(recs)
    st.session_state["recommendations"] = recs

recs = st.session_state.get("recommendations")
if recs is None:
    recs = generate_recommendations(
        state=state,
        price_history=prices,
        strategy_name=state.strategy,
        strategy_params=settings.get("strategy_params", {}),
        max_allocation_per_stock=float(settings.get("max_allocation_per_stock", 0.20)),
        min_trade_value=float(settings.get("min_trade_value", 50.0)),
        minimum_price_band_pct=float(settings.get("minimum_price_band_pct", 0.01)),
    )

show_cols = ["date", "ticker", "action", "current_shares", "target_shares", "share_delta", "latest_price", "price_range_low", "price_range_high", "estimated_cash_impact", "target_weight"]
st.dataframe(recs[show_cols], use_container_width=True)

st.subheader("Record executions")
actionable = recs[recs["action"].isin(["BUY", "SELL"])].copy()
if actionable.empty:
    st.info("No actionable buy/sell recommendations for the current settings.")
else:
    for _, row in actionable.iterrows():
        with st.expander(f"{row['action']} {abs(row['share_delta']):.0f} shares of {row['ticker']}"):
            st.write(f"Suggested range: ${row['price_range_low']:.2f} – ${row['price_range_high']:.2f}")
            executed = st.checkbox("Executed", key=f"executed_{row['date']}_{row['ticker']}")
            c1, c2 = st.columns(2)
            with c1:
                default_shares = float(abs(row["share_delta"])) if executed else 0.0
                shares = st.number_input("Executed shares", min_value=0.0, value=default_shares, step=1.0, key=f"shares_{row['date']}_{row['ticker']}")
            with c2:
                price = st.number_input("Executed price", min_value=0.0, value=float(row["latest_price"]), step=0.01, key=f"price_{row['date']}_{row['ticker']}")
            notes = st.text_input("Notes", key=f"notes_{row['date']}_{row['ticker']}")
            if st.button("Save execution status", key=f"save_{row['date']}_{row['ticker']}"):
                try:
                    state = load_portfolio_state()
                    log_row = apply_execution(state, row["ticker"], row["action"], executed, shares, price, notes)
                    append_execution_log(log_row)
                    st.success("Execution status saved and portfolio state updated if executed.")
                except Exception as exc:
                    st.error(str(exc))
