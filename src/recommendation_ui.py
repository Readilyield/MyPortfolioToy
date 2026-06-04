from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src.execution_engine import apply_execution, append_execution_log, load_execution_log
from src.data_loader import normalize_ticker
from src.portfolio_state import PortfolioState, load_portfolio_state, save_portfolio_state
from src.recommendation_engine import generate_recommendations, save_daily_recommendations
from src.strategy_registry import STRATEGY_FACTORIES


DAILY_ACTION_CAP = 10
VISIBLE_ACTION_LIMIT = 5
MARKET_TZ = ZoneInfo("America/New_York")
MARKET_CLOSE_TIME = time(16, 0)


ACTION_CSS = """
<style>
.action-title {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 1.04rem;
    font-weight: 700;
    line-height: 1.35;
    margin-bottom: 0.15rem;
}
.action-subtitle {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 0.9rem;
    color: rgba(49, 51, 63, 0.78);
    line-height: 1.35;
}
.action-pill-buy,
.action-pill-sell {
    display: inline-block;
    border-radius: 999px;
    padding: 0.18rem 0.62rem;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 0.88rem;
    font-weight: 800;
    letter-spacing: 0.02em;
    color: white !important;
}
.action-pill-buy {
    background: #00C853;
}
.action-pill-sell {
    background: #FF1744;
}
.action-metric-label {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 0.78rem;
    color: rgba(49, 51, 63, 0.65);
    line-height: 1.1;
}
.action-metric-value {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 0.96rem;
    font-weight: 650;
    line-height: 1.25;
}
.small-muted {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 0.86rem;
    color: rgba(49, 51, 63, 0.72);
}
</style>
"""


def _setup_done(state: PortfolioState) -> bool:
    return bool(state.holdings) or float(state.cash or 0.0) > 0


def _configured_strategy_params(state: PortfolioState) -> dict[str, dict]:
    """Return strategy-specific params saved through Initial Setup."""
    settings = state.settings or {}
    configured = settings.get("strategy_params_by_strategy", {}) or {}

    # Backward compatibility for older state files. The single strategy_params block
    # belongs only to the currently saved strategy and should not be shared across
    # other strategy constructors.
    if state.strategy and state.strategy not in configured and settings.get("strategy_params"):
        configured = dict(configured)
        configured[state.strategy] = settings.get("strategy_params", {})
    return configured


def _strategy_params_for_state(state: PortfolioState) -> dict:
    configured = _configured_strategy_params(state)
    if state.strategy not in configured:
        raise ValueError(
            f"{state.strategy} has not been configured yet. Open Initial Setup, select {state.strategy}, "
            "review its parameters, and save setup before using it on the recommendation page."
        )
    return configured[state.strategy]


def ensure_strategy_selector(state: PortfolioState, key_prefix: str = "strategy") -> tuple[PortfolioState, bool]:
    """Render selector. Only allow switching to strategies that were saved in setup."""
    names = list(STRATEGY_FACTORIES.keys())
    current = state.strategy if state.strategy in names else names[0]
    selected = st.selectbox(
        "Strategy",
        names,
        index=names.index(current),
        key=f"{key_prefix}_selectbox",
        help=(
            "Switching is allowed only for strategies already saved in Initial Setup. "
            "This prevents parameters from one strategy being accidentally passed into another."
        ),
    )

    configured = _configured_strategy_params(state)
    if selected != state.strategy:
        if selected not in configured:
            st.error(
                f"{selected} has not been set up yet. Open **Initial Setup**, choose **{selected}**, "
                "review/save its parameters, then return to this page to use it."
            )
            st.info(f"Continuing with the currently configured strategy: **{state.strategy}**.")
            return state, False

        state.strategy = selected
        state.settings["strategy_params"] = configured[selected]
        save_portfolio_state(state)
        st.session_state.pop(f"{key_prefix}_recommendations", None)
        st.toast(f"Strategy switched to {selected}")
    return state, True


def _now_eastern() -> datetime:
    return datetime.now(MARKET_TZ)


def _market_closed_for_today(now: datetime | None = None) -> bool:
    now = now or _now_eastern()
    return now.time() >= MARKET_CLOSE_TIME


def _active_recommendation_date(now: datetime | None = None) -> str:
    """Return the date key for the current recommendation queue.

    Recommendations are only visible before 4:00 PM Eastern. After that, the
    queue is considered cleared for the day and no new action rows are shown.
    """
    now = now or _now_eastern()
    return now.date().isoformat()


def _action_identity(row: pd.Series) -> str:
    return "|".join([
        str(row.get("date", "")),
        str(row.get("strategy", "")),
        str(row.get("ticker", "")),
        str(row.get("action", "")),
    ])


def _completed_action_ids(action_date: str, strategy: str) -> set[str]:
    log = load_execution_log()
    if log.empty:
        return set()
    needed = {"date", "ticker", "recommended_action"}
    if not needed.issubset(log.columns):
        return set()

    subset = log[log["date"].astype(str).eq(str(action_date))].copy()
    if subset.empty:
        return set()

    # Newer rows include the strategy. Older logs do not, so keep them compatible
    # and treat same-date/ticker/action rows as completed for any strategy.
    if "strategy" in subset.columns:
        subset = subset[(subset["strategy"].isna()) | (subset["strategy"].astype(str).eq(str(strategy)))]

    ids = set()
    for _, row in subset.iterrows():
        ids.add("|".join([
            str(row.get("date", "")),
            str(row.get("strategy", strategy) if pd.notna(row.get("strategy", strategy)) else strategy),
            str(row.get("ticker", "")),
            str(row.get("recommended_action", "")),
        ]))
        # Backward-compatible id for logs that do not have a strategy column.
        ids.add("|".join([
            str(row.get("date", "")),
            str(strategy),
            str(row.get("ticker", "")),
            str(row.get("recommended_action", "")),
        ]))
    return ids


def _pending_action_queue(recs: pd.DataFrame, action_date: str, strategy: str) -> pd.DataFrame:
    if recs.empty:
        return pd.DataFrame()
    queue = _rank_actionable(recs).head(DAILY_ACTION_CAP).copy()
    if queue.empty:
        return queue
    queue["date"] = action_date
    completed_ids = _completed_action_ids(action_date, strategy)
    if not completed_ids:
        return queue.reset_index(drop=True)
    mask = ~queue.apply(lambda row: _action_identity(row) in completed_ids, axis=1)
    return queue[mask].reset_index(drop=True)


def build_recommendations_for_state(state: PortfolioState, prices: pd.DataFrame) -> pd.DataFrame:
    settings = state.settings or {}
    recs = generate_recommendations(
        state=state,
        price_history=prices,
        strategy_name=state.strategy,
        strategy_params=_strategy_params_for_state(state),
        max_allocation_per_stock=float(settings.get("max_allocation_per_stock", 0.20)),
        min_trade_value=float(settings.get("min_trade_value", 50.0)),
        minimum_price_band_pct=float(settings.get("minimum_price_band_pct", 0.01)),
        max_daily_actions=DAILY_ACTION_CAP,
    )
    if not recs.empty:
        recs["date"] = _active_recommendation_date()
    return recs


def _rank_actionable(recs: pd.DataFrame) -> pd.DataFrame:
    if recs.empty or "action" not in recs:
        return pd.DataFrame()
    actionable = recs[recs["action"].isin(["BUY", "SELL"])].copy()
    if actionable.empty:
        return actionable
    actionable["rank_value"] = actionable["estimated_cash_impact"].abs().fillna(0.0)
    return actionable.sort_values(["rank_value", "ticker"], ascending=[False, True]).drop(columns=["rank_value"])


def render_recommendation_table(recs: pd.DataFrame) -> None:
    st.subheader("All recommendations")
    if recs.empty:
        st.warning("No recommendations could be generated. Check whether price data is available.")
        return
    show_cols = [
        "date", "ticker", "action", "current_shares", "target_shares", "share_delta",
        "latest_price", "price_range_low", "price_range_high", "estimated_cash_impact", "target_weight",
    ]
    display = recs[[c for c in show_cols if c in recs.columns]].copy()
    st.dataframe(
        display,
        use_container_width=True,
        column_config={
            "current_shares": st.column_config.NumberColumn(format="%.6f"),
            "target_shares": st.column_config.NumberColumn(format="%.6f"),
            "share_delta": st.column_config.NumberColumn(format="%.6f"),
            "latest_price": st.column_config.NumberColumn(format="$%.2f"),
            "price_range_low": st.column_config.NumberColumn(format="$%.2f"),
            "price_range_high": st.column_config.NumberColumn(format="$%.2f"),
            "estimated_cash_impact": st.column_config.NumberColumn(format="$%.2f"),
            "target_weight": st.column_config.NumberColumn(format="%.2%%"),
        },
    )


def render_execution_cards(recs: pd.DataFrame, key_prefix: str = "exec", limit: int = VISIBLE_ACTION_LIMIT, strategy: str = "") -> None:
    st.markdown(ACTION_CSS, unsafe_allow_html=True)
    st.subheader("Recommended actions")

    now = _now_eastern()
    if _market_closed_for_today(now):
        st.info("The daily recommendation queue is cleared after 4:00 PM Eastern when the market closes. Generate a new queue on the next trading day.")
        return

    action_date = _active_recommendation_date(now)
    actionable = _pending_action_queue(recs, action_date=action_date, strategy=strategy).head(limit)
    pending_count = len(_pending_action_queue(recs, action_date=action_date, strategy=strategy))
    if actionable.empty:
        st.info("No pending buy/sell recommendations remain for today. Executed or skipped actions are hidden from this page.")
        return

    st.caption(
        f"Showing {len(actionable)} of {pending_count} pending actions for {action_date}. "
        f"The daily queue is capped at {DAILY_ACTION_CAP} actions and is cleared after 4:00 PM Eastern."
    )

    for rank, (_, row) in enumerate(actionable.iterrows(), start=1):
        ticker = str(row["ticker"])
        date = str(row["date"])
        action = str(row["action"])
        key_base = f"{key_prefix}_{date}_{ticker}_{action}"
        default_shares = float(abs(row.get("share_delta", 0.0)))
        default_price = float(row.get("latest_price", 0.0))
        cash_impact = float(row.get("estimated_cash_impact", 0.0))
        low = row.get("price_range_low")
        high = row.get("price_range_high")
        range_text = "N/A"
        if pd.notna(low) and pd.notna(high):
            range_text = f"${float(low):,.2f} – ${float(high):,.2f}"

        pill = "action-pill-buy" if action == "BUY" else "action-pill-sell"
        with st.expander(f"#{rank} {action} {ticker} — {default_shares:,.6g} shares", expanded=rank == 1):
            top_left, top_mid, top_right = st.columns([2.4, 1.3, 1.2], vertical_alignment="center")
            with top_left:
                st.markdown(
                    f"""
                    <div class="action-title"><span class="{pill}">{action}</span> {ticker}</div>
                    <div class="action-subtitle">Recommended quantity: {default_shares:,.6g} shares</div>
                    <div class="small-muted">Suggested price range: <strong>{range_text}</strong></div>
                    """,
                    unsafe_allow_html=True,
                )
            with top_mid:
                st.markdown(
                    f"""
                    <div class="action-metric-label">Latest price</div>
                    <div class="action-metric-value">${default_price:,.2f}</div>
                    <div class="action-metric-label" style="margin-top:0.35rem">Est. cash impact</div>
                    <div class="action-metric-value">${cash_impact:,.2f}</div>
                    """,
                    unsafe_allow_html=True,
                )
            with top_right:
                if st.button(f"Execute {action}", key=f"{key_base}_execute_btn", type="primary", use_container_width=True):
                    shares = float(st.session_state.get(f"{key_base}_shares", default_shares))
                    price = float(st.session_state.get(f"{key_base}_price", default_price))
                    notes = str(st.session_state.get(f"{key_base}_notes", ""))
                    try:
                        latest_state = load_portfolio_state()
                        log_row = apply_execution(latest_state, ticker, action, True, shares, price, notes)
                        log_row["date"] = date
                        log_row["strategy"] = strategy or str(row.get("strategy", ""))
                        append_execution_log(log_row)
                        st.success(f"Recorded executed {action} for {ticker} and updated portfolio state.")
                        st.session_state.pop(key_prefix.replace("_cards", "_recommendations"), None)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

            st.markdown(
                "<div class='small-muted'>Defaults below come from the strategy recommendation. Adjust them before clicking Execute if your actual order differs.</div>",
                unsafe_allow_html=True,
            )
            i1, i2, i3 = st.columns([1, 1, 2])
            with i1:
                st.number_input(
                    "Executed shares",
                    min_value=0.0,
                    value=default_shares,
                    step=1.0,
                    format="%.6f",
                    key=f"{key_base}_shares",
                )
            with i2:
                st.number_input(
                    "Executed price",
                    min_value=0.0,
                    value=default_price,
                    step=0.01,
                    format="%.4f",
                    key=f"{key_base}_price",
                )
            with i3:
                st.text_input("Notes", key=f"{key_base}_notes", placeholder="Optional")

            if st.button("Save as not executed", key=f"{key_base}_skip_btn"):
                try:
                    latest_state = load_portfolio_state()
                    log_row = apply_execution(latest_state, ticker, action, False, 0.0, default_price, "Not executed")
                    log_row["date"] = date
                    log_row["strategy"] = strategy or str(row.get("strategy", ""))
                    append_execution_log(log_row)
                    st.info(f"Recorded {ticker} recommendation as not executed.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


def render_custom_action_box(key_prefix: str = "custom_action") -> None:
    """Allow the user to manually record a buy/sell action outside strategy recommendations."""
    st.markdown(ACTION_CSS, unsafe_allow_html=True)
    st.subheader("Custom action")
    st.caption(
        "Use this to record a manual buy/sell that is not generated by the strategy. "
        "The ticker can be any Yahoo-compatible stock or ETF symbol."
    )

    with st.form(f"{key_prefix}_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns([1.2, 0.9, 1.0, 1.0])
        with c1:
            ticker_raw = st.text_input("Ticker", placeholder="Example: DUOL, LULU, IGV", key=f"{key_prefix}_ticker")
        with c2:
            action = st.selectbox("Action", ["BUY", "SELL"], key=f"{key_prefix}_action")
        with c3:
            shares = st.number_input("Shares", min_value=0.0, value=0.0, step=1.0, format="%.6f", key=f"{key_prefix}_shares")
        with c4:
            price = st.number_input("Executed price", min_value=0.0, value=0.0, step=0.01, format="%.4f", key=f"{key_prefix}_price")
        notes = st.text_input("Notes", placeholder="Optional note for this custom action", key=f"{key_prefix}_notes")
        submitted = st.form_submit_button("Record custom action", type="primary", use_container_width=True)

    if submitted:
        ticker = normalize_ticker(ticker_raw)
        if not ticker:
            st.error("Please enter a ticker.")
            return
        if shares <= 0:
            st.error("Shares must be greater than zero.")
            return
        if price <= 0:
            st.error("Executed price must be greater than zero.")
            return
        try:
            latest_state = load_portfolio_state()
            log_row = apply_execution(latest_state, ticker, action, True, shares, price, notes)
            log_row["date"] = _active_recommendation_date()
            log_row["strategy"] = "CUSTOM"
            log_row["source"] = "custom_action"
            append_execution_log(log_row)
            st.success(f"Recorded custom {action} for {ticker} and updated portfolio state.")
            st.info(
                "If this ticker is outside the NASDAQ-100 universe, open Data Update and refresh tracked supplemental tickers "
                "so the Portfolio Tracker can monitor its price history."
            )
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render_recommendation_dashboard(prices: pd.DataFrame, key_prefix: str = "dashboard", show_full_table: bool = True) -> None:
    state = load_portfolio_state()
    if not _setup_done(state):
        st.info("Initial setup is not complete yet. Open Initial Setup, enter cash and holdings, then return here for strategy recommendations.")
        return

    state, strategy_ready = ensure_strategy_selector(state, key_prefix=key_prefix)
    if not strategy_ready:
        return

    if prices.empty:
        st.error("Price data is empty. Open Data Update or check the local data files.")
        return

    try:
        params = _strategy_params_for_state(state)
    except ValueError as exc:
        st.error(str(exc))
        return

    latest_date = prices.index[-1].date().isoformat()
    st.caption(f"Strategy universe: NASDAQ-100 only | Latest data date: {latest_date}")
    st.caption("Current strategy parameters: " + ", ".join(f"{k}={v}" for k, v in params.items()))
    st.info("Non-NASDAQ-100 holdings are tracked passively and included in portfolio monitoring when supplemental prices are available. They are not bought or sold by the strategy engine.")

    if _market_closed_for_today():
        st.info("The market is closed for today. Daily recommendations are cleared after 4:00 PM Eastern and will be available again on the next trading day.")
        return

    rec_key = f"{key_prefix}_recommendations"
    col_a, col_b = st.columns([1, 4])
    with col_a:
        refresh = st.button("Generate / refresh", type="primary", key=f"{key_prefix}_refresh", use_container_width=True)
    if refresh or st.session_state.get(rec_key) is None:
        try:
            recs = build_recommendations_for_state(state, prices)
        except TypeError as exc:
            st.error(
                "This strategy could not be built with the currently saved parameters. "
                "Open Initial Setup, select this strategy, save its parameter set, then return here."
            )
            st.exception(exc)
            return
        except Exception as exc:
            st.error(f"Recommendation generation failed: {exc}")
            return
        save_daily_recommendations(recs)
        st.session_state[rec_key] = recs
    else:
        recs = st.session_state[rec_key]

    render_execution_cards(recs, key_prefix=f"{key_prefix}_cards", limit=VISIBLE_ACTION_LIMIT, strategy=state.strategy)
    st.divider()
    render_custom_action_box(key_prefix=f"{key_prefix}_custom")
    if show_full_table:
        render_recommendation_table(recs)
