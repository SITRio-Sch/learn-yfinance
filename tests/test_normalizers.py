"""Unit tests for pure data normalizers."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from yf_learner.providers.raw_models import (
    RawAnalystData,
    RawFundamentalsData,
    RawHistoryData,
    RawNewsData,
    RawQuoteData,
    RawSearchResults,
    RawStatementData,
    RawTable,
)
from yf_learner.services.normalizers import (
    clean_datetime,
    clean_float,
    clean_int,
    clean_str,
    normalize_analyst,
    normalize_fundamentals,
    normalize_history,
    normalize_news,
    normalize_quote,
    normalize_search,
    normalize_statement,
)


def test_clean_primitives():
    # clean_str
    assert clean_str("  AAPL  ") == "AAPL"
    assert clean_str("NaN") is None
    assert clean_str("None") is None
    assert clean_str("null") is None
    assert clean_str("nat") is None
    assert clean_str("") is None
    assert clean_str(None) is None

    # clean_float
    assert clean_float(123.45) == 123.45
    assert clean_float("1,234.56") == 1234.56
    assert clean_float(float("nan")) is None
    assert clean_float(float("inf")) is None
    assert clean_float("NaN") is None
    assert clean_float(None) is None

    # clean_int
    assert clean_int(100) == 100
    assert clean_int(100.0) == 100
    assert clean_int("1,000") == 1000
    assert clean_int(float("nan")) is None
    assert clean_int(None) is None

    # clean_datetime
    now = datetime.now(timezone.utc)
    assert clean_datetime(now) == now
    assert clean_datetime("2026-03-01T12:00:00Z") == datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert clean_datetime(1710000000) == datetime.fromtimestamp(1710000000, tz=timezone.utc)
    assert clean_datetime("invalid") is None
    assert clean_datetime(None) is None


def test_normalize_search_max_eight():
    retrieved_at = datetime.now(timezone.utc)
    raw_quotes = [
        {"symbol": f"SYM{i}", "shortname": f"Company {i}", "exchange": "NYQ", "quoteType": "EQUITY"}
        for i in range(15)
    ]
    raw = RawSearchResults(raw_quotes=raw_quotes, retrieved_at=retrieved_at)
    res = normalize_search(raw, "SYM")
    assert len(res.items) == 8
    assert res.items[0].symbol == "SYM0"
    assert res.provenance.source == "Yahoo Finance via yfinance"
    assert res.provenance.data_as_of is None


def test_normalize_quote_missing_and_nans():
    retrieved_at = datetime.now(timezone.utc)
    raw = RawQuoteData(
        symbol="XYZ",
        fast_info={
            "last_price": float("nan"),
            "previous_close": None,
            "day_high": "NaN",
            "volume": None,
            "currency": "USD",
        },
        history_metadata={
            "regularMarketTime": 1710000000,
        },
        retrieved_at=retrieved_at,
    )
    res = normalize_quote(raw)
    assert res.symbol == "XYZ"
    assert res.last_price is None
    assert res.previous_close is None
    assert res.day_high is None
    assert res.volume is None
    assert res.currency == "USD"
    assert res.provenance is not None
    assert res.provenance.data_as_of == datetime.fromtimestamp(1710000000, tz=timezone.utc)


def test_normalize_history_empty_and_complete():
    retrieved_at = datetime.now(timezone.utc)
    # Empty table
    raw_empty = RawHistoryData(
        symbol="AAPL",
        period="1mo",
        interval="1d",
        auto_adjust=True,
        actions=False,
        table=RawTable(columns=(), index=(), data=()),
        retrieved_at=retrieved_at,
    )
    res_empty = normalize_history(raw_empty)
    assert len(res_empty.points) == 0
    assert res_empty.provenance.data_as_of is None

    # Complete table with corporate actions
    raw_full = RawHistoryData(
        symbol="AAPL",
        period="1mo",
        interval="1d",
        auto_adjust=True,
        actions=True,
        table=RawTable(
            columns=("Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"),
            index=("2026-01-02", "2026-01-03"),
            data=(
                (150.0, 155.0, 149.0, 153.0, 1000000, 0.25, 0.0),
                (153.0, 154.0, 151.0, 152.0, 1200000, 0.0, 0.0),
            ),
        ),
        retrieved_at=retrieved_at,
    )
    res_full = normalize_history(raw_full)
    assert len(res_full.points) == 2
    assert res_full.points[0].open == 150.0
    assert res_full.points[0].dividends == 0.25
    assert res_full.provenance.data_as_of == datetime(2026, 1, 3, 0, 0, tzinfo=timezone.utc)


def test_normalize_fundamentals_clean():
    retrieved_at = datetime.now(timezone.utc)
    raw = RawFundamentalsData(
        symbol="TEST",
        info={
            "shortName": "Test Corp",
            "marketCap": 1000000000,
            "trailingPE": float("nan"),
            "longBusinessSummary": "A test company description.",
        },
        retrieved_at=retrieved_at,
    )
    res = normalize_fundamentals(raw)
    assert res.name == "Test Corp"
    assert res.market_cap == 1000000000.0
    assert res.trailing_pe is None
    assert res.business_summary == "A test company description."


def test_normalize_statement():
    retrieved_at = datetime.now(timezone.utc)
    raw = RawStatementData(
        symbol="TEST",
        statement="Income statement",
        frequency="yearly",
        table=RawTable(
            columns=("2025-12-31", "2024-12-31"),
            index=("Revenue", "Net Income"),
            data=((50000, 45000), (10000, 8000)),
        ),
        retrieved_at=retrieved_at,
    )
    res = normalize_statement(raw)
    assert res.symbol == "TEST"
    assert res.table.columns == ("2025-12-31", "2024-12-31")
    assert res.table.rows[0] == (50000.0, 45000.0)
    assert res.provenance.data_as_of == datetime(2025, 12, 31, 0, 0, tzinfo=timezone.utc)


def test_normalize_analyst():
    retrieved_at = datetime.now(timezone.utc)
    raw_targets = RawAnalystData(
        symbol="TEST",
        dataset="price_targets",
        table=None,
        targets_dict={"current": 100.0, "low": 80.0, "high": 120.0, "mean": 105.0, "median": 102.0},
        retrieved_at=retrieved_at,
    )
    res_targets = normalize_analyst(raw_targets)
    assert res_targets.targets is not None
    assert res_targets.targets.current == 100.0
    assert res_targets.targets.mean == 105.0


def test_normalize_news_both_formats():
    retrieved_at = datetime.now(timezone.utc)
    raw = RawNewsData(
        symbol="TEST",
        feed="news",
        raw_items=[
            # Format 1: nested content
            {
                "content": {
                    "title": "Article 1",
                    "provider": {"displayName": "Reuters"},
                    "canonicalUrl": {"url": "https://example.com/1"},
                    "pubDate": "2026-03-01T10:00:00Z",
                    "id": "uuid-1",
                }
            },
            # Format 2: flat keys
            {
                "title": "Article 2",
                "publisher": "Bloomberg",
                "link": "https://example.com/2",
                "providerPublishTime": 1710005000,
                "uuid": "uuid-2",
            },
        ],
        retrieved_at=retrieved_at,
    )
    res = normalize_news(raw)
    assert len(res.items) == 2
    assert res.items[0].title == "Article 1"
    assert res.items[0].publisher == "Reuters"
    assert res.items[1].title == "Article 2"
    assert res.items[1].publisher == "Bloomberg"
    assert res.provenance.data_as_of is not None
