from __future__ import annotations

import pandas as pd
import streamlit as st

from src.recommendation_engine import load_recommendation_log
from src.execution_engine import load_execution_log

st.set_page_config(page_title="Action History", layout="wide")
st.title("Action History")

recs = load_recommendation_log()
execs = load_execution_log()

tab1, tab2 = st.tabs(["Recommendation Log", "Execution Log"])

with tab1:
    st.subheader("Recommendations")
    if recs.empty:
        st.info("No recommendations have been saved yet.")
    else:
        tickers = sorted(recs["ticker"].dropna().unique().tolist())
        selected = st.multiselect("Filter tickers", tickers, default=[])
        filtered = recs.copy()
        if selected:
            filtered = filtered[filtered["ticker"].isin(selected)]
        st.dataframe(filtered, use_container_width=True)
        st.download_button("Download recommendation log", filtered.to_csv(index=False), "recommendation_log.csv")

with tab2:
    st.subheader("Executions")
    if execs.empty:
        st.info("No execution statuses have been saved yet.")
    else:
        executed_only = st.checkbox("Show executed trades only")
        filtered = execs[execs["executed"].astype(str).str.lower().isin(["true", "1"])] if executed_only else execs
        st.dataframe(filtered, use_container_width=True)
        st.download_button("Download execution log", filtered.to_csv(index=False), "execution_log.csv")
