"""UI presentation components and formatting helpers."""

from __future__ import annotations

from typing import Any

import streamlit as st

from yf_learner.domain.errors import DataProblem
from yf_learner.domain.models import (
    AnalystResult,
    FundamentalsResult,
    HistoryResult,
    NewsResult,
    QuoteSnapshot,
    StatementResult,
    TableData,
)
from yf_learner.ui.cache import (
    cached_analyst,
    cached_fundamentals,
    cached_history,
    cached_news,
    cached_quote,
    cached_statement,
)
from yf_learner.ui.teaching import (
    CODE_SNIPPETS,
    TEACHING_COPY,
    format_provenance_markdown,
)

NOT_AVAILABLE = "Not available"


def format_val(
    val: Any,
    prefix: str = "",
    suffix: str = "",
    decimals: int | None = None,
    format_large: bool = False,
) -> str:
    """Format a value for display, returning 'Not available' for missing data."""
    if val is None:
        return NOT_AVAILABLE
    if isinstance(val, (int, float)):
        if format_large and abs(val) >= 1_000_000:
            if abs(val) >= 1_000_000_000_000:
                return f"{prefix}{val / 1_000_000_000_000:.2f}T{suffix}"
            if abs(val) >= 1_000_000_000:
                return f"{prefix}{val / 1_000_000_000:.2f}B{suffix}"
            return f"{prefix}{val / 1_000_000:.2f}M{suffix}"

        if decimals is not None:
            return f"{prefix}{val:,.{decimals}f}{suffix}"
        if isinstance(val, int):
            return f"{prefix}{val:,}{suffix}"
        return f"{prefix}{val:,}{suffix}"

    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null", "nat"):
        return NOT_AVAILABLE
    return f"{prefix}{s}{suffix}"


def render_problem(problem: DataProblem) -> None:
    """Display a user-friendly error notice without raw tracebacks."""
    st.error(problem.message)
    if problem.details:
        st.caption(problem.details)


def render_notice() -> None:
    """Display educational purpose, provider limitations, and explicit action model."""
    st.title("Learn yFinance")
    st.markdown(
        """
Welcome to **Learn yFinance**, an interactive educational workbench designed to teach you how the popular
open-source `yfinance` Python library queries financial market data from Yahoo Finance.

> **Important Educational Notes & Yahoo Finance Limitations:**
> - **Educational Only:** This application is strictly read-only and designed for learning data engineering and market analysis concepts. It does not support trading, brokerage integration, alerts, or investment recommendations.
> - **Provider Boundaries:** Yahoo Finance does not provide an official public API for free access. The `yfinance` library queries unofficial endpoints and scrapes web pages, meaning requests may be rate-limited, delayed, or intermittently unavailable.
> - **Zero Automatic Network Requests:** To respect network resources and rate limits, this application performs **zero** Yahoo Finance network calls on initial page load. Requests happen **only** after you explicitly submit a search or click an action.
"""
    )


def render_quote_tab(symbol: str) -> None:
    """Render the Quote tab."""
    st.subheader("Quote Snapshot")
    st.markdown(TEACHING_COPY["quote"])

    col_btn, _ = st.columns([2, 8])
    with col_btn:
        if st.button("Refresh quote", key="btn_refresh_quote"):
            st.session_state["refresh_quote"] = st.session_state.get("refresh_quote", 0) + 1

    token = st.session_state.get("refresh_quote", 0)
    with st.spinner("Loading live quote…"):
        result = cached_quote(symbol, token=token)

    if result.problem is not None:
        render_problem(result.problem)
        st.markdown(format_provenance_markdown(None, limitation_key="quote"))
        return

    snapshot = result.value
    if snapshot is None:
        st.warning("No quote data available for this ticker.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Last Price", format_val(snapshot.last_price, prefix="$", decimals=2))
        st.metric("Open", format_val(snapshot.open_price, prefix="$", decimals=2))
        st.metric("Currency", format_val(snapshot.currency))
    with col2:
        st.metric("Previous Close", format_val(snapshot.previous_close, prefix="$", decimals=2))
        day_h = format_val(snapshot.day_high, prefix="$", decimals=2)
        day_l = format_val(snapshot.day_low, prefix="$", decimals=2)
        st.metric("Day High / Low", f"{day_h} / {day_l}")
        st.metric("Exchange", format_val(snapshot.exchange))
    with col3:
        w_h = format_val(snapshot.fifty_two_week_high, prefix="$", decimals=2)
        w_l = format_val(snapshot.fifty_two_week_low, prefix="$", decimals=2)
        st.metric("52-Week Range", f"{w_l} - {w_h}")
        st.metric("Volume", format_val(snapshot.volume))
        st.metric("Timezone", format_val(snapshot.timezone))
    with col4:
        st.metric("Avg Volume (3M)", format_val(snapshot.average_volume))
        st.metric("Avg Volume (10D)", format_val(snapshot.average_volume_10d))
        st.metric("Market Cap", format_val(snapshot.market_cap, prefix="$", format_large=True))

    with st.expander("What yfinance is doing"):
        st.code(CODE_SNIPPETS["quote"].format(symbol=symbol), language="python")

    st.markdown(format_provenance_markdown(snapshot.provenance, limitation_key="quote"))


def render_history_tab(symbol: str) -> None:
    """Render the History tab."""
    st.subheader("Historical Prices & Volume")
    st.markdown(TEACHING_COPY["history"])

    c1, c2, c3, c4, c5 = st.columns([2, 2, 3, 3, 2])
    with c1:
        period = st.selectbox(
            "Period",
            ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"],
            index=0,
            key="history_period_sel",
        )
    with c2:
        interval = st.selectbox(
            "Interval",
            ["1d", "1wk", "1mo"],
            index=0,
            key="history_interval_sel",
        )
    with c3:
        auto_adjust = st.checkbox(
            "Auto-adjust prices",
            value=True,
            key="history_auto_adj_cb",
        )
    with c4:
        actions = st.checkbox(
            "Include corporate actions",
            value=False,
            key="history_actions_cb",
        )
    with c5:
        if st.button("Refresh history", key="btn_refresh_history"):
            st.session_state["refresh_history"] = st.session_state.get("refresh_history", 0) + 1

    token = st.session_state.get("refresh_history", 0)
    with st.spinner("Loading live history…"):
        result = cached_history(
            symbol,
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            actions=actions,
            token=token,
        )

    if result.problem is not None:
        render_problem(result.problem)
        st.markdown(format_provenance_markdown(None, limitation_key="history"))
        return

    hist: HistoryResult | None = result.value
    if hist is None or not hist.points:
        st.info("No historical price records returned for this configuration.")
        return

    # Render summary metric
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Records", len(hist.points))
    with m2:
        st.metric("Start Date", hist.points[0].date_or_time or NOT_AVAILABLE)
    with m3:
        st.metric("End Date", hist.points[-1].date_or_time or NOT_AVAILABLE)
    with m4:
        latest_close = format_val(hist.points[-1].close, prefix="$", decimals=2)
        st.metric("Latest Close", latest_close)

    # Format table records
    table_rows = []
    chart_dates = []
    chart_closes = []
    for p in hist.points:
        chart_dates.append(p.date_or_time)
        chart_closes.append(p.close)
        row = {
            "Date": p.date_or_time,
            "Open": format_val(p.open, decimals=2),
            "High": format_val(p.high, decimals=2),
            "Low": format_val(p.low, decimals=2),
            "Close": format_val(p.close, decimals=2),
            "Volume": format_val(p.volume),
        }
        if actions:
            row["Dividends"] = format_val(p.dividends, decimals=4)
            row["Stock Splits"] = format_val(p.stock_splits)
        table_rows.append(row)

    # Render line chart of closing prices
    if any(c is not None for c in chart_closes):
        chart_data = {
            "Date": chart_dates,
            "Close": chart_closes,
        }
        st.line_chart(chart_data, x="Date", y="Close")

    st.dataframe(table_rows, width="stretch")

    with st.expander("What yfinance is doing"):
        snippet = CODE_SNIPPETS["history"].format(
            symbol=symbol,
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            actions=actions,
        )
        st.code(snippet, language="python")

    st.markdown(format_provenance_markdown(hist.provenance, limitation_key="history"))


def render_fundamentals_tab(symbol: str) -> None:
    """Render the Fundamentals tab."""
    st.subheader("Company Fundamentals")
    st.markdown(TEACHING_COPY["fundamentals"])

    col_btn, _ = st.columns([2, 8])
    with col_btn:
        if st.button("Refresh fundamentals", key="btn_refresh_fundamentals"):
            st.session_state["refresh_fundamentals"] = st.session_state.get("refresh_fundamentals", 0) + 1

    token = st.session_state.get("refresh_fundamentals", 0)
    with st.spinner("Loading live fundamentals…"):
        result = cached_fundamentals(symbol, token=token)

    if result.problem is not None:
        render_problem(result.problem)
        st.markdown(format_provenance_markdown(None, limitation_key="fundamentals"))
        return

    fund: FundamentalsResult | None = result.value
    if fund is None:
        st.warning("No fundamental data available for this ticker.")
        return

    st.markdown("#### Profile & Classification")
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown(f"**Company Name:** {format_val(fund.name)}")
        st.markdown(f"**Quote Type:** {format_val(fund.quote_type)}")
        st.markdown(f"**Exchange:** {format_val(fund.exchange)}")
    with p2:
        st.markdown(f"**Sector:** {format_val(fund.sector)}")
        st.markdown(f"**Industry:** {format_val(fund.industry)}")
        st.markdown(f"**Country:** {format_val(fund.country)}")
    with p3:
        st.markdown(f"**Currency:** {format_val(fund.currency)}")
        st.markdown(f"**Employees:** {format_val(fund.employees)}")
        st.markdown(f"**Website:** {format_val(fund.website)}")

    st.markdown("#### Valuation & Financial Ratios")
    v1, v2, v3, v4 = st.columns(4)
    with v1:
        st.metric("Market Cap", format_val(fund.market_cap, prefix="$", format_large=True))
        st.metric("Enterprise Value", format_val(fund.enterprise_value, prefix="$", format_large=True))
    with v2:
        st.metric("Trailing P/E", format_val(fund.trailing_pe, decimals=2))
        st.metric("Forward P/E", format_val(fund.forward_pe, decimals=2))
    with v3:
        st.metric("Price / Book", format_val(fund.price_to_book, decimals=2))
        div_str = (
            f"{fund.dividend_yield * 100:.2f}%"
            if fund.dividend_yield is not None
            else NOT_AVAILABLE
        )
        st.metric("Dividend Yield", div_str)
    with v4:
        st.metric("Beta (Volatility)", format_val(fund.beta, decimals=2))

    if fund.business_summary:
        st.markdown("#### Business Summary")
        st.info(fund.business_summary)

    with st.expander("What yfinance is doing"):
        st.code(CODE_SNIPPETS["fundamentals"].format(symbol=symbol), language="python")

    st.markdown(format_provenance_markdown(fund.provenance, limitation_key="fundamentals"))


def render_statements_tab(symbol: str) -> None:
    """Render the Financial Statements tab."""
    st.subheader("Financial Statements")
    st.markdown(TEACHING_COPY["statements"])

    c1, c2, c3 = st.columns([3, 3, 2])
    with c1:
        statement = st.selectbox(
            "Statement",
            ["Income statement", "Balance sheet", "Cash flow"],
            key="stmt_type_sel",
        )
    with c2:
        freq_label = st.selectbox(
            "Frequency",
            ["Annual", "Quarterly"],
            key="stmt_freq_sel",
        )
        frequency = "yearly" if freq_label == "Annual" else "quarterly"
    with c3:
        if st.button("Refresh financial statements", key="btn_refresh_statements"):
            st.session_state["refresh_statements"] = st.session_state.get("refresh_statements", 0) + 1

    token = st.session_state.get("refresh_statements", 0)
    with st.spinner("Loading live financial statements…"):
        result = cached_statement(symbol, statement=statement, frequency=frequency, token=token)

    if result.problem is not None:
        render_problem(result.problem)
        st.markdown(format_provenance_markdown(None, limitation_key="statements"))
        return

    stmt: StatementResult | None = result.value
    if stmt is None or not stmt.table.columns or not stmt.table.index:
        st.info(f"No {statement.lower()} data available for this frequency.")
        return

    # Render tabular display
    display_data = []
    for r_idx, metric_name in enumerate(stmt.table.index):
        row_dict: dict[str, Any] = {"Metric": metric_name}
        row_vals = stmt.table.rows[r_idx] if r_idx < len(stmt.table.rows) else ()
        for c_idx, col_name in enumerate(stmt.table.columns):
            val = row_vals[c_idx] if c_idx < len(row_vals) else None
            row_dict[col_name] = format_val(val, format_large=True)
        display_data.append(row_dict)

    st.dataframe(display_data, width="stretch")

    with st.expander("What yfinance is doing"):
        method_map = {
            "Income statement": "get_income_stmt",
            "Balance sheet": "get_balance_sheet",
            "Cash flow": "get_cash_flow",
        }
        snippet = CODE_SNIPPETS["statements"].format(
            symbol=symbol,
            method=method_map.get(statement, "get_income_stmt"),
            freq=frequency,
        )
        st.code(snippet, language="python")

    st.markdown(format_provenance_markdown(stmt.provenance, limitation_key="statements"))


def render_analyst_tab(symbol: str) -> None:
    """Render the Analyst Data tab."""
    st.subheader("Analyst Data & Estimates")
    st.markdown(TEACHING_COPY["analyst"])

    dataset_options = {
        "recommendations": "Analyst Recommendations",
        "price_targets": "Price Targets",
        "earnings_estimate": "Earnings Estimates",
        "revenue_estimate": "Revenue Estimates",
        "growth_estimates": "Growth Estimates",
    }

    c1, c2 = st.columns([4, 2])
    with c1:
        dataset = st.selectbox(
            "Dataset",
            list(dataset_options.keys()),
            format_func=lambda k: dataset_options[k],
            key="analyst_dataset_sel",
        )
    with c2:
        if st.button("Refresh analyst data", key="btn_refresh_analyst"):
            st.session_state["refresh_analyst"] = st.session_state.get("refresh_analyst", 0) + 1

    token = st.session_state.get("refresh_analyst", 0)
    with st.spinner("Loading live analyst data…"):
        result = cached_analyst(symbol, dataset=dataset, token=token)

    if result.problem is not None:
        render_problem(result.problem)
        st.markdown(format_provenance_markdown(None, limitation_key="analyst"))
        return

    analyst: AnalystResult | None = result.value
    if analyst is None:
        st.info(f"No {dataset_options[dataset].lower()} available for this ticker.")
        return

    if analyst.targets is not None:
        # Render price targets cards
        t = analyst.targets
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("Current", format_val(t.current, prefix="$", decimals=2))
        with c2:
            st.metric("Low Target", format_val(t.low, prefix="$", decimals=2))
        with c3:
            st.metric("Mean Target", format_val(t.mean, prefix="$", decimals=2))
        with c4:
            st.metric("Median Target", format_val(t.median, prefix="$", decimals=2))
        with c5:
            st.metric("High Target", format_val(t.high, prefix="$", decimals=2))
    elif analyst.table is not None and analyst.table.columns:
        display_data = []
        for r_idx, idx_name in enumerate(analyst.table.index):
            row_dict: dict[str, Any] = {"Item": idx_name}
            row_vals = analyst.table.rows[r_idx] if r_idx < len(analyst.table.rows) else ()
            for c_idx, col_name in enumerate(analyst.table.columns):
                val = row_vals[c_idx] if c_idx < len(row_vals) else None
                row_dict[col_name] = format_val(val)
            display_data.append(row_dict)
        st.dataframe(display_data, width="stretch")
    else:
        st.info(f"No {dataset_options[dataset].lower()} available for this ticker.")

    with st.expander("What yfinance is doing"):
        method_map = {
            "recommendations": "get_recommendations",
            "price_targets": "get_analyst_price_targets",
            "earnings_estimate": "get_earnings_estimate",
            "revenue_estimate": "get_revenue_estimate",
            "growth_estimates": "get_growth_estimates",
        }
        snippet = CODE_SNIPPETS["analyst"].format(
            symbol=symbol,
            method=method_map.get(dataset, "get_recommendations"),
        )
        st.code(snippet, language="python")

    st.markdown(format_provenance_markdown(analyst.provenance, limitation_key="analyst"))


def render_news_tab(symbol: str) -> None:
    """Render the News tab."""
    st.subheader("News & Corporate Releases")
    st.markdown(TEACHING_COPY["news"])

    c1, c2, c3 = st.columns([3, 3, 2])
    with c1:
        feed = st.selectbox(
            "Feed",
            ["news", "all", "press releases"],
            key="news_feed_sel",
        )
    with c2:
        count = st.slider("Articles Count", min_value=1, max_value=20, value=8, key="news_count_slider")
    with c3:
        if st.button("Refresh news", key="btn_refresh_news"):
            st.session_state["refresh_news"] = st.session_state.get("refresh_news", 0) + 1

    token = st.session_state.get("refresh_news", 0)
    with st.spinner("Loading live news…"):
        result = cached_news(symbol, feed=feed, count=count, token=token)

    if result.problem is not None:
        render_problem(result.problem)
        st.markdown(format_provenance_markdown(None, limitation_key="news"))
        return

    news: NewsResult | None = result.value
    if news is None or not news.items:
        st.info("No news articles are available for this ticker.")
        return

    for item in news.items:
        title = item.title or "Untitled"
        publisher = item.publisher or NOT_AVAILABLE
        published = (
            item.published_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            if item.published_at
            else NOT_AVAILABLE
        )

        with st.container():
            if item.link:
                st.markdown(f"##### [{title}]({item.link})")
            else:
                st.markdown(f"##### {title}")
            st.caption(f"Publisher: **{publisher}** | Published: **{published}**")
            st.divider()

    with st.expander("What yfinance is doing"):
        snippet = CODE_SNIPPETS["news"].format(
            symbol=symbol,
            count=count,
            feed=feed,
        )
        st.code(snippet, language="python")

    st.markdown(format_provenance_markdown(news.provenance, limitation_key="news"))
