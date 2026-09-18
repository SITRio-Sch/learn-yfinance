"""Main Streamlit application entry point."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from yf_learner.domain.models import SearchResultItem
from yf_learner.ui.cache import cached_search
from yf_learner.ui.components import (
    render_analyst_tab,
    render_fundamentals_tab,
    render_history_tab,
    render_news_tab,
    render_notice,
    render_problem,
    render_quote_tab,
    render_statements_tab,
)
from yf_learner.ui.layout import render_controls_row

TAB_NAMES = [
    "Quote",
    "History",
    "Fundamentals",
    "Financial Statements",
    "Analyst Data",
    "News",
]


def init_session_state() -> None:
    """Initialize necessary session state variables."""
    for token_key in (
        "refresh_quote",
        "refresh_history",
        "refresh_fundamentals",
        "refresh_statements",
        "refresh_analyst",
        "refresh_news",
    ):
        if token_key not in st.session_state:
            st.session_state[token_key] = 0

    if "search_results" not in st.session_state:
        st.session_state["search_results"] = None

    if "active_symbol" not in st.session_state:
        st.session_state["active_symbol"] = None


def is_tab_active(tab: st.delta_generator.DeltaGenerator, tab_name: str) -> bool:
    """Determine if a tab container is active (lazy rendering guard)."""
    if hasattr(tab, "open"):
        return bool(tab.open)
    return st.session_state.get("learning_tab") == tab_name


def load_stylesheet() -> None:
    """Load scoped CSS stylesheet once immediately after page config."""
    css_path = Path(__file__).resolve().parent / "styles.css"
    if css_path.exists():
        css_content = css_path.read_text(encoding="utf-8")
        st.html(f"<style>\n{css_content}\n</style>")


def render_app() -> None:
    """Render the primary Streamlit application."""
    st.set_page_config(
        page_title="Learn yFinance",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    load_stylesheet()

    init_session_state()

    # 1. Notice and Title (Initial render performs ZERO Yahoo requests)
    render_notice()
    st.divider()

    # 2. Search Section
    st.subheader("Search Tickers")
    with st.form(key="search_form", clear_on_submit=False):
        query_input = st.text_input(
            "Enter company name or ticker symbol (e.g. AAPL, MSFT, Toyota):",
            key="search_query_input",
        )
        submitted = st.form_submit_button("Search", use_container_width=False)

    if submitted:
        trimmed = query_input.strip()
        if not trimmed:
            st.warning("Please enter a non-empty search query.")
            st.session_state["search_results"] = None
        else:
            with st.spinner("Searching Yahoo Finance…"):
                res = cached_search(trimmed, token=0)
            if res.problem is not None:
                render_problem(res.problem)
                st.session_state["search_results"] = None
            else:
                st.session_state["search_results"] = res.value.items if res.value else ()
                st.session_state["last_query"] = trimmed

    # Display Search Results if available
    results = st.session_state.get("search_results")
    if results is not None:
        if len(results) == 0:
            st.info(f"No search results returned for '{st.session_state.get('last_query', '')}'.")
        else:
            st.markdown(f"**Found {len(results)} matches (select one, then click Open ticker):**")

            def format_search_item(item: SearchResultItem) -> str:
                name = item.name or "N/A"
                exchange = item.exchange or "N/A"
                quote_type = item.quote_type or "N/A"
                return f"{item.symbol} — {name} ({exchange}, {quote_type})"

            selected_item = st.radio(
                "Select a ticker from search results:",
                options=results,
                format_func=format_search_item,
                key="search_results_radio",
                label_visibility="visible",
            )

            with render_controls_row():
                if st.button("Open ticker", key="open_ticker_btn", type="primary"):
                    if selected_item:
                        st.session_state["active_symbol"] = selected_item.symbol

    # 3. Active Ticker and Six Lazy Tabs
    active_symbol = st.session_state.get("active_symbol")
    if active_symbol:
        st.divider()
        st.markdown(f"### Active Ticker: `{active_symbol}`")

        # Expose exactly six lazy tabs
        tab_quote, tab_history, tab_fund, tab_stmt, tab_analyst, tab_news = st.tabs(
            TAB_NAMES,
            key="learning_tab",
            on_change="rerun",
        )

        with tab_quote:
            if is_tab_active(tab_quote, "Quote"):
                render_quote_tab(active_symbol)

        with tab_history:
            if is_tab_active(tab_history, "History"):
                render_history_tab(active_symbol)

        with tab_fund:
            if is_tab_active(tab_fund, "Fundamentals"):
                render_fundamentals_tab(active_symbol)

        with tab_stmt:
            if is_tab_active(tab_stmt, "Financial Statements"):
                render_statements_tab(active_symbol)

        with tab_analyst:
            if is_tab_active(tab_analyst, "Analyst Data"):
                render_analyst_tab(active_symbol)

        with tab_news:
            if is_tab_active(tab_news, "News"):
                render_news_tab(active_symbol)


if __name__ == "__main__":
    render_app()
