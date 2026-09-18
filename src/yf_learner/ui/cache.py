"""Session-scoped caching layer for MarketDataService calls."""

from __future__ import annotations

import streamlit as st

from yf_learner.domain.models import (
    AnalystResult,
    DataResult,
    FundamentalsResult,
    HistoryResult,
    NewsResult,
    QuoteSnapshot,
    SearchResults,
    StatementResult,
)
from yf_learner.services.market_data import MarketDataService
from yf_learner.services.normalizers import FUNDAMENTALS_NORMALIZATION_SCHEMA_VERSION

_GLOBAL_SERVICE_OVERRIDE: MarketDataService | None = None


def set_service_override(service: MarketDataService | None) -> None:
    """Set global service override for testing."""
    global _GLOBAL_SERVICE_OVERRIDE
    _GLOBAL_SERVICE_OVERRIDE = service


def get_service() -> MarketDataService:
    """Retrieve the current MarketDataService instance."""
    if "_market_data_service" in st.session_state:
        return st.session_state["_market_data_service"]
    global _GLOBAL_SERVICE_OVERRIDE
    if _GLOBAL_SERVICE_OVERRIDE is not None:
        return _GLOBAL_SERVICE_OVERRIDE

    from yf_learner.providers.yfinance_provider import YFinanceProvider

    service = MarketDataService(YFinanceProvider())
    st.session_state["_market_data_service"] = service
    return service


@st.cache_data(ttl=600, scope="session", show_spinner=False)
def cached_search(query: str, token: int = 0) -> DataResult[SearchResults]:
    """Cache search results for 600 seconds."""
    return get_service().search(query)


@st.cache_data(ttl=60, scope="session", show_spinner=False)
def cached_quote(symbol: str, token: int = 0) -> DataResult[QuoteSnapshot]:
    """Cache quote snapshots for 60 seconds."""
    return get_service().quote(symbol)


@st.cache_data(ttl=300, scope="session", show_spinner=False)
def cached_history(
    symbol: str,
    period: str,
    interval: str,
    auto_adjust: bool,
    actions: bool,
    token: int = 0,
) -> DataResult[HistoryResult]:
    """Cache history time-series for 300 seconds."""
    return get_service().history(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
        actions=actions,
    )


@st.cache_data(ttl=1800, scope="session", show_spinner=False)
def _cached_fundamentals_versioned(
    symbol: str,
    normalization_schema_version: int,
    token: str = "default",
) -> DataResult[FundamentalsResult]:
    """Internal session-scoped cache for fundamentals, keyed by symbol, schema version, and token."""
    return get_service().fundamentals(symbol)


def cached_fundamentals(symbol: str, token: str = "default") -> DataResult[FundamentalsResult]:
    """Cache fundamentals for 1800 seconds with versioned schema cache key."""
    return _cached_fundamentals_versioned(
        symbol=symbol,
        normalization_schema_version=FUNDAMENTALS_NORMALIZATION_SCHEMA_VERSION,
        token=token,
    )


@st.cache_data(ttl=3600, scope="session", show_spinner=False)
def cached_statement(
    symbol: str,
    statement: str,
    frequency: str,
    token: int = 0,
) -> DataResult[StatementResult]:
    """Cache financial statements for 3600 seconds."""
    return get_service().financial_statement(symbol, statement, frequency)


@st.cache_data(ttl=900, scope="session", show_spinner=False)
def cached_analyst(
    symbol: str,
    dataset: str,
    token: str = "default",
) -> DataResult[AnalystResult]:
    """Cache analyst estimates/targets for 900 seconds."""
    return get_service().analyst_data(symbol, dataset)


@st.cache_data(ttl=300, scope="session", show_spinner=False)
def cached_news(
    symbol: str,
    feed: str,
    count: int,
    token: int = 0,
) -> DataResult[NewsResult]:
    """Cache news articles for 300 seconds."""
    return get_service().news(symbol, feed=feed, count=count)
