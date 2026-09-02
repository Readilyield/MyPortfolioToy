from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.data_loader import load_price_matrix, load_tracking_price_matrix, latest_prices, load_ndx_series, load_ticker_universe
from src.portfolio_state import (
    load_portfolio_state,
    save_portfolio_state,
    portfolio_value,
    holdings_market_table,
    append_portfolio_snapshot,
    frame_to_holdings,
    holdings_to_frame,
)
from src.recommendation_engine import compute_target_weights
from src.plotting import plot_current_vs_target, plot_portfolio_value, plot_nav_vs_benchmark
from src.paths import NASDAQ_PRICES_PATH, NDX_PRICES_PATH, SNAPSHOT_LOG_PATH

st.set_page_config(page_title="Portfolio Tracker", layout="wide")
st.title("Portfolio Tracker")

@st.cache_data(show_spinner=False)
def cached_prices(holding_tickers: tuple[str, ...]):
    return load_tracking_price_matrix(set(holding_tickers))


def _tracking_start_from_state(state) -> date:
    raw = (state.settings or {}).get("tracking_start_date")
    if raw:
        try:
            return pd.to_datetime(raw).date()
        except Exception:
            pass
    return date.today()


def _filter_from_start(df: pd.DataFrame, start: date) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return df
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    return out[out["date"].dt.date >= start].sort_values("date")


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
tracking_start = _tracking_start_from_state(state)

c1, c2, c3 = st.columns(3)
c1.metric("Cash", f"${state.cash:,.2f}")
c2.metric("Total Portfolio Value", f"${value:,.2f}")
c3.metric("Latest Data Date", prices.index[-1].date().isoformat() if not prices.empty else "N/A")

st.subheader("Edit Portfolio Holdings")
with st.expander("Change cash, shares, average cost, or tickers", expanded=False):
    st.caption(
        "Use this when your broker holdings changed outside the app. "
        "Set shares to 0 or delete a row to remove a holding. "
        "Custom tickers and ETFs are allowed."
    )
    edited_cash = st.number_input(
        "Current cash balance",
        min_value=0.0,
        value=float(state.cash),
        step=100.0,
        format="%.2f",
    )
    holdings_df = holdings_to_frame(state)
    edited_holdings = st.data_editor(
        holdings_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "ticker": st.column_config.TextColumn(
                "Ticker",
                help="Any Yahoo-compatible ticker, for example AAPL, DUOL, LULU, IGV, or BRK-B.",
                required=True,
            ),
            "shares": st.column_config.NumberColumn(
                "Shares",
                min_value=0.0,
                step=0.0001,
                format="%.4f",
                required=True,
            ),
            "average_cost": st.column_config.NumberColumn(
                "Average cost",
                min_value=0.0,
                step=0.01,
                format="%.4f",
            ),
        },
        key="editable_portfolio_holdings",
    )
    save_holdings = st.button("Save portfolio changes", type="primary", use_container_width=True)
    if save_holdings:
        try:
            state.cash = float(edited_cash)
            state.holdings = frame_to_holdings(edited_holdings)
            save_portfolio_state(state)
            cached_prices.clear()
            st.success("Portfolio holdings updated.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save portfolio changes: {exc}")

st.subheader("Save Portfolio Snapshot")
st.caption(
    "Save the current cash, holdings, market value, and strategy into "
    "storage/portfolio_snapshots.csv. This local file powers the historical "
    "performance chart below and is ignored by Git."
)
snap_c1, snap_c2, snap_c3 = st.columns([1, 1, 2])
with snap_c1:
    snapshot_date = st.date_input("Snapshot date", value=date.today())
with snap_c2:
    st.write("")
    st.write("")
    save_snapshot_clicked = st.button("Save snapshot", type="primary", use_container_width=True)
with snap_c3:
    st.write("")
    st.write("")
    st.caption("Saving again for the same date replaces the previous row for that date.")

if save_snapshot_clicked:
    if prices.empty or latest.empty:
        st.error("Cannot save a snapshot because no latest prices are loaded. Refresh market data first.")
    else:
        saved = append_portfolio_snapshot(state, latest, snapshot_date=snapshot_date.isoformat())
        st.success(
            f"Saved snapshot for {saved['date']}: "
            f"portfolio value ${saved['portfolio_value']:,.2f}, "
            f"{saved['holding_count']} holdings."
        )
        st.rerun()

with st.expander("Performance tracking start date", expanded=False):
    new_start = st.date_input(
        "Track portfolio performance from",
        value=tracking_start,
        help=(
            "Saved portfolio snapshots before this date are hidden from the performance chart. "
            "Use the home page button 'Save today’s portfolio snapshot' to build the tracked history."
        ),
    )
    if st.button("Save tracking start date", type="primary"):
        state.settings = state.settings or {}
        state.settings["tracking_start_date"] = new_start.isoformat()
        save_portfolio_state(state)
        st.success(f"Tracking start date saved: {new_start.isoformat()}")
        st.rerun()

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
st.caption(f"Showing saved snapshots from {tracking_start.isoformat()} onward.")
try:
    snapshots = pd.read_csv(SNAPSHOT_LOG_PATH)
except FileNotFoundError:
    snapshots = pd.DataFrame()

tracked_snapshots = _filter_from_start(snapshots, tracking_start)
fig = plot_portfolio_value(tracked_snapshots)
if fig is not None:
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No saved snapshots are available for the selected tracking period. Use the Save snapshot button above to create one.")

if not tracked_snapshots.empty:
    display_cols = [
        col
        for col in [
            "date",
            "cash",
            "invested_value",
            "portfolio_value",
            "cash_weight",
            "holding_count",
            "strategy",
            "snapshot_timestamp",
        ]
        if col in tracked_snapshots.columns
    ]
    with st.expander("View saved snapshots", expanded=False):
        st.dataframe(tracked_snapshots[display_cols], use_container_width=True, hide_index=True)
        st.download_button(
            "Download portfolio_snapshots.csv",
            data=tracked_snapshots.to_csv(index=False),
            file_name="portfolio_snapshots.csv",
            mime="text/csv",
            use_container_width=True,
        )

if not tracked_snapshots.empty and "portfolio_value" in tracked_snapshots.columns:
    normalized = tracked_snapshots.copy()
    normalized["date"] = pd.to_datetime(normalized["date"])
    normalized = normalized.dropna(subset=["portfolio_value"])
    if len(normalized) >= 1 and float(normalized["portfolio_value"].iloc[0]) != 0:
        nav = normalized.set_index("date")["portfolio_value"].astype(float)
        st.subheader("Normalized Performance Since Tracking Start")
        st.caption("This uses your saved portfolio snapshots and normalizes the first snapshot in the selected period to 1.0.")
        try:
            ndx = load_ndx_series(NDX_PRICES_PATH)
            ndx = ndx[ndx.index.date >= tracking_start]
            st.plotly_chart(plot_nav_vs_benchmark(nav, ndx), use_container_width=True)
        except Exception as exc:
            st.warning(f"Could not load NDX benchmark for normalized comparison: {exc}")
            st.line_chart((nav / nav.iloc[0]).rename("Portfolio"))

st.subheader("Benchmark")
try:
    ndx = load_ndx_series(NDX_PRICES_PATH)
    ndx = ndx[ndx.index.date >= tracking_start]
    if ndx.empty:
        st.info("No NDX benchmark data is available after the selected tracking start date.")
    else:
        st.line_chart((ndx / ndx.iloc[0]).rename("Normalized NDX"))
except Exception as exc:
    st.warning(f"Could not load NDX benchmark: {exc}")
