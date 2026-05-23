from __future__ import annotations

import json

import streamlit as st

from src.data_loader import load_price_matrix
from src.market_data import load_data_metadata, refresh_market_data, get_ticker_universe
from src.paths import NASDAQ_PRICES_PATH, NDX_PRICES_PATH, DATA_METADATA_PATH

st.set_page_config(page_title="Data Update", layout="wide")
st.title("Data Update")
st.caption("Refresh NASDAQ-100 daily prices and the NDX benchmark from the internet.")

st.warning(
    "The app downloads market data for personal research and educational use. "
    "Check the latest data date before relying on any recommendation."
)

metadata = load_data_metadata()
if metadata:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Last Refresh UTC", metadata.get("refreshed_at_utc", "N/A")[:19])
    c2.metric("Downloaded Tickers", metadata.get("tickers_downloaded", "N/A"))
    c3.metric("Start Date", metadata.get("start_date", "N/A"))
    c4.metric("End Date", metadata.get("end_date", "N/A"))
else:
    st.info("No refresh metadata found yet. The app is currently using the bundled local CSV files.")

try:
    local_prices = load_price_matrix(NASDAQ_PRICES_PATH)
    st.write(f"Current local price file: `{NASDAQ_PRICES_PATH}`")
    st.write(f"Current local shape: **{local_prices.shape[0]} dates × {local_prices.shape[1]} tickers**")
    if not local_prices.empty:
        st.write(f"Current local date range: **{local_prices.index.min().date()}** to **{local_prices.index.max().date()}**")
except Exception as exc:
    st.error(f"Could not load current local price file: {exc}")

st.subheader("Refresh settings")
period = st.selectbox("Historical period", ["1y", "2y", "5y", "10y", "max"], index=2)
interval = st.selectbox("Interval", ["1d", "1wk", "1mo"], index=0)
use_live_wikipedia = st.checkbox("Refresh current NASDAQ-100 ticker universe from Wikipedia", value=True)

with st.expander("Preview ticker universe"):
    try:
        tickers = get_ticker_universe(use_live_wikipedia=False)
        st.write(f"Local ticker count: {len(tickers)}")
        st.write(", ".join(tickers[:120]))
    except Exception as exc:
        st.warning(f"Could not load local ticker universe: {exc}")

if st.button("Download latest market data", type="primary"):
    with st.spinner("Downloading NASDAQ-100 prices and NDX benchmark..."):
        try:
            result = refresh_market_data(
                period=period,
                interval=interval,
                use_live_wikipedia=use_live_wikipedia,
                price_path=NASDAQ_PRICES_PATH,
                ndx_path=NDX_PRICES_PATH,
            )
            st.cache_data.clear()
            st.success(
                f"Refresh complete: {result.rows_written:,} stock price rows, "
                f"{result.tickers_downloaded}/{result.tickers_requested} tickers, "
                f"date range {result.start_date} to {result.end_date}."
            )
            st.write(f"Updated stock file: `{result.price_path}`")
            st.write(f"Updated benchmark file: `{result.ndx_path}`")
            st.write(f"Metadata file: `{result.metadata_path}`")
        except Exception as exc:
            st.error(f"Refresh failed: {exc}")
            st.info(
                "Common fixes: check your internet connection, install `yfinance`, or disable the live Wikipedia ticker refresh "
                "to use the local ticker universe."
            )

st.subheader("Refresh metadata")
if DATA_METADATA_PATH.exists():
    try:
        st.json(json.loads(DATA_METADATA_PATH.read_text(encoding="utf-8")))
    except Exception:
        st.write(DATA_METADATA_PATH.read_text(encoding="utf-8"))
else:
    st.caption("No metadata file yet.")
