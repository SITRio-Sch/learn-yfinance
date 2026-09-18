"""UI presentation components and formatting helpers."""

from __future__ import annotations

import math
from typing import Any
from uuid import uuid4

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
from yf_learner.services.normalizers import clean_datetime
from yf_learner.ui.cache import (
    cached_analyst,
    cached_fundamentals,
    cached_history,
    cached_news,
    cached_quote,
    cached_statement,
)
from yf_learner.ui.layout import (
    build_analyst_table_column_config,
    build_history_column_config,
    build_statement_column_config,
    render_controls_row,
    render_dataframe,
    render_metric_grid,
    render_profile_grid,
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
        if math.isnan(val) or math.isinf(val):
            return NOT_AVAILABLE
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


def format_percent(val: float | None, decimals: int = 2) -> str:
    """Format a canonical fractional ratio (e.g. 0.0032 -> 0.32%) as percentage."""
    if val is None:
        return NOT_AVAILABLE
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return NOT_AVAILABLE
        return f"{val * 100:.{decimals}f}%"
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null", "nat"):
        return NOT_AVAILABLE
    try:
        f = float(s)
        if math.isnan(f) or math.isinf(f):
            return NOT_AVAILABLE
        return f"{f * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return NOT_AVAILABLE


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

    with render_controls_row():
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

    day_h = format_val(snapshot.day_high, prefix="$", decimals=2)
    day_l = format_val(snapshot.day_low, prefix="$", decimals=2)
    day_range = f"{day_h} / {day_l}" if (day_h != NOT_AVAILABLE or day_l != NOT_AVAILABLE) else NOT_AVAILABLE

    w_h = format_val(snapshot.fifty_two_week_high, prefix="$", decimals=2)
    w_l = format_val(snapshot.fifty_two_week_low, prefix="$", decimals=2)
    range_52w = f"{w_l} - {w_h}" if (w_l != NOT_AVAILABLE or w_h != NOT_AVAILABLE) else NOT_AVAILABLE

    metrics = [
        ("Last Price", format_val(snapshot.last_price, prefix="$", decimals=2)),
        ("Previous Close", format_val(snapshot.previous_close, prefix="$", decimals=2)),
        ("Open", format_val(snapshot.open_price, prefix="$", decimals=2)),
        ("Day High / Low", day_range),
        ("52-Week Range", range_52w),
        ("Volume", format_val(snapshot.volume)),
        ("Avg Volume (3M)", format_val(snapshot.average_volume)),
        ("Avg Volume (10D)", format_val(snapshot.average_volume_10d)),
        ("Market Cap", format_val(snapshot.market_cap, prefix="$", format_large=True)),
        ("Currency", format_val(snapshot.currency)),
        ("Exchange", format_val(snapshot.exchange)),
        ("Timezone", format_val(snapshot.timezone)),
    ]
    render_metric_grid(metrics, max_columns=4)

    with st.expander("What yfinance is doing"):
        st.code(CODE_SNIPPETS["quote"].format(symbol=symbol), language="python")

    st.markdown(format_provenance_markdown(snapshot.provenance, limitation_key="quote"))


def render_history_tab(symbol: str) -> None:
    """Render the History tab."""
    st.subheader("Historical Prices & Volume")
    st.markdown(TEACHING_COPY["history"])

    with render_controls_row():
        period = st.selectbox(
            "Period",
            ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"],
            index=0,
            key="history_period_sel",
        )
        interval = st.selectbox(
            "Interval",
            ["1d", "1wk", "1mo"],
            index=0,
            key="history_interval_sel",
        )
        auto_adjust = st.checkbox(
            "Auto-adjust prices",
            value=True,
            key="history_auto_adj_cb",
        )
        actions = st.checkbox(
            "Include corporate actions",
            value=False,
            key="history_actions_cb",
        )
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

    latest_close = format_val(hist.points[-1].close, prefix="$", decimals=2)
    summary_metrics = [
        ("Total Records", str(len(hist.points))),
        ("Start Date", hist.points[0].date_or_time or NOT_AVAILABLE),
        ("End Date", hist.points[-1].date_or_time or NOT_AVAILABLE),
        ("Latest Close", latest_close),
    ]
    render_metric_grid(summary_metrics, max_columns=4)

    # Format table records & chart series
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

    # Render line chart of closing prices with parsed dates for temporal axis
    if any(c is not None for c in chart_closes):
        parsed_dates = []
        for d in chart_dates:
            try:
                dt = clean_datetime(d)
                parsed_dates.append(dt if dt is not None else d)
            except Exception:
                parsed_dates.append(d)

        chart_data = {
            "Date": parsed_dates,
            "Close": chart_closes,
        }
        st.line_chart(chart_data, x="Date", y="Close", height=350)

    col_config = build_history_column_config(actions=actions)
    render_dataframe(table_rows, column_config=col_config)

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

    with render_controls_row():
        if st.button("Refresh fundamentals", key="btn_refresh_fundamentals"):
            st.session_state["refresh_fundamentals"] = uuid4().hex

    token = st.session_state.get("refresh_fundamentals", "default")
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
    website_val = fund.website
    if website_val and website_val.startswith(("http://", "https://")):
        website_disp = f"[{website_val}]({website_val})"
    else:
        website_disp = format_val(website_val)

    profile_items = [
        ("Company Name", format_val(fund.name)),
        ("Quote Type", format_val(fund.quote_type)),
        ("Exchange", format_val(fund.exchange)),
        ("Sector", format_val(fund.sector)),
        ("Industry", format_val(fund.industry)),
        ("Country", format_val(fund.country)),
        ("Currency", format_val(fund.currency)),
        ("Employees", format_val(fund.employees)),
        ("Website", website_disp),
    ]
    render_profile_grid(profile_items, columns=3)

    st.markdown("#### Valuation & Financial Ratios")
    val_metrics = [
        ("Market Cap", format_val(fund.market_cap, prefix="$", format_large=True)),
        ("Enterprise Value", format_val(fund.enterprise_value, prefix="$", format_large=True)),
        ("Trailing P/E", format_val(fund.trailing_pe, decimals=2)),
        ("Forward P/E", format_val(fund.forward_pe, decimals=2)),
        ("Price / Book", format_val(fund.price_to_book, decimals=2)),
        ("Dividend Yield", format_percent(fund.dividend_yield)),
        ("Beta (Volatility)", format_val(fund.beta, decimals=2)),
    ]
    render_metric_grid(val_metrics, max_columns=4)

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

    with render_controls_row():
        statement = st.selectbox(
            "Statement",
            ["Income statement", "Balance sheet", "Cash flow"],
            key="stmt_type_sel",
        )
        freq_label = st.selectbox(
            "Frequency",
            ["Annual", "Quarterly"],
            key="stmt_freq_sel",
        )
        frequency = "yearly" if freq_label == "Annual" else "quarterly"
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

    col_config = build_statement_column_config(stmt.table.columns, metric_column_name="Metric")
    render_dataframe(display_data, column_config=col_config)

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

    with render_controls_row():
        dataset = st.selectbox(
            "Dataset",
            list(dataset_options.keys()),
            format_func=lambda k: dataset_options[k],
            key="analyst_dataset_sel",
        )
        if st.button("Refresh analyst data", key="btn_refresh_analyst"):
            st.session_state["refresh_analyst"] = uuid4().hex

    token = st.session_state.get("refresh_analyst", "default")
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
        t = analyst.targets
        targets_metrics = [
            ("Current", format_val(t.current, prefix="$", decimals=2)),
            ("Low Target", format_val(t.low, prefix="$", decimals=2)),
            ("Mean Target", format_val(t.mean, prefix="$", decimals=2)),
            ("Median Target", format_val(t.median, prefix="$", decimals=2)),
            ("High Target", format_val(t.high, prefix="$", decimals=2)),
        ]
        render_metric_grid(targets_metrics, max_columns=5)
    elif analyst.table is not None and analyst.table.columns:
        display_data = []
        for r_idx, idx_name in enumerate(analyst.table.index):
            row_dict: dict[str, Any] = {"Item": idx_name}
            row_vals = analyst.table.rows[r_idx] if r_idx < len(analyst.table.rows) else ()
            for c_idx, col_name in enumerate(analyst.table.columns):
                val = row_vals[c_idx] if c_idx < len(row_vals) else None
                row_dict[col_name] = format_val(val)
            display_data.append(row_dict)
        col_config = build_analyst_table_column_config(analyst.table.columns, item_column_name="Item")
        render_dataframe(display_data, column_config=col_config)
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

    with render_controls_row():
        feed = st.selectbox(
            "Feed",
            ["news", "all", "press releases"],
            key="news_feed_sel",
        )
        count = st.slider("Articles Count", min_value=1, max_value=20, value=8, key="news_count_slider")
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

        with st.container(border=True):
            if item.link:
                st.markdown(f"##### [{title}]({item.link})")
            else:
                st.markdown(f"##### {title}")
            st.caption(f"**Publisher:** {publisher} | **Published:** {published}")

    with st.expander("What yfinance is doing"):
        snippet = CODE_SNIPPETS["news"].format(
            symbol=symbol,
            count=count,
            feed=feed,
        )
        st.code(snippet, language="python")

    st.markdown(format_provenance_markdown(news.provenance, limitation_key="news"))
