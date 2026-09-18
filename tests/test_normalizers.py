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
    FUNDAMENTALS_NORMALIZATION_SCHEMA_VERSION,
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
from yf_learner.ui.components import NOT_AVAILABLE, format_percent


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
            "dividendYield": 0.55,
            "longBusinessSummary": "A test company description.",
        },
        retrieved_at=retrieved_at,
    )
    res = normalize_fundamentals(raw)
    assert res.name == "Test Corp"
    assert res.market_cap == 1000000000.0
    assert res.trailing_pe is None
    assert res.dividend_yield == 0.0055
    assert res.business_summary == "A test company description."


def test_normalize_fundamentals_dividend_yield_percentage_points_to_ratio():
    retrieved_at = datetime.now(timezone.utc)

    # Apple-like 0.32 percentage points -> 0.0032 fractional ratio
    raw_apple = RawFundamentalsData(
        symbol="AAPL",
        info={"dividendYield": 0.32},
        retrieved_at=retrieved_at,
    )
    res_apple = normalize_fundamentals(raw_apple)
    assert res_apple.dividend_yield == 0.0032

    # High-yield stock 2.5 percentage points -> 0.025 fractional ratio
    raw_high = RawFundamentalsData(
        symbol="DIV",
        info={"dividendYield": 2.5},
        retrieved_at=retrieved_at,
    )
    res_high = normalize_fundamentals(raw_high)
    assert res_high.dividend_yield == 0.025

    # Zero dividend yield
    raw_zero = RawFundamentalsData(
        symbol="ZERO",
        info={"dividendYield": 0.0},
        retrieved_at=retrieved_at,
    )
    res_zero = normalize_fundamentals(raw_zero)
    assert res_zero.dividend_yield == 0.0


def test_normalize_fundamentals_dividend_yield_missing_and_malformed():
    retrieved_at = datetime.now(timezone.utc)
    for invalid_val in [None, float("nan"), "nan", "NaN", "None", "null", "undefined", "invalid"]:
        raw = RawFundamentalsData(
            symbol="NONE",
            info={"dividendYield": invalid_val},
            retrieved_at=retrieved_at,
        )
        res = normalize_fundamentals(raw)
        assert res.dividend_yield is None, f"Expected None for raw value {invalid_val!r}"


def test_fundamentals_normalization_schema_version_constant():
    """Ensure normalization schema version constant is exported and positive integer."""
    assert isinstance(FUNDAMENTALS_NORMALIZATION_SCHEMA_VERSION, int)
    assert FUNDAMENTALS_NORMALIZATION_SCHEMA_VERSION >= 2


def test_dividend_yield_normalizer_and_format_percent_end_to_end():
    """Verify dividendYield normalization to canonical ratio and format_percent end-to-end."""
    retrieved_at = datetime.now(timezone.utc)

    # Required regression cases: raw 0.32 -> 0.0032 -> "0.32%", along with 0.55, 2.5, 0.0, None, NaN, malformed
    cases = [
        (0.32, 0.0032, "0.32%"),
        (0.55, 0.0055, "0.55%"),
        (2.5, 0.025, "2.50%"),
        (0.0, 0.0, "0.00%"),
        (None, None, NOT_AVAILABLE),
        (float("nan"), None, NOT_AVAILABLE),
        ("NaN", None, NOT_AVAILABLE),
        ("nan", None, NOT_AVAILABLE),
        ("None", None, NOT_AVAILABLE),
        ("null", None, NOT_AVAILABLE),
        ("invalid", None, NOT_AVAILABLE),
    ]

    for raw_val, expected_ratio, expected_display in cases:
        raw = RawFundamentalsData(
            symbol="TEST",
            info={"dividendYield": raw_val},
            retrieved_at=retrieved_at,
        )
        res = normalize_fundamentals(raw)
        assert res.dividend_yield == expected_ratio, (
            f"Expected canonical ratio {expected_ratio} for raw {raw_val!r}, got {res.dividend_yield}"
        )
        formatted = format_percent(res.dividend_yield)
        assert formatted == expected_display, (
            f"Expected formatted string {expected_display!r} for raw {raw_val!r}, got {formatted!r}"
        )


def test_normalize_statement_long_metric_identifiers():
    retrieved_at = datetime.now(timezone.utc)
    raw = RawStatementData(
        symbol="LONG",
        statement="Income statement",
        frequency="yearly",
        table=RawTable(
            columns=("2025-09-30", "2024-09-30"),
            index=(
                "NetIncomeFromContinuingOperationNetMinorityInterest",
                "OperatingIncomeContinuousOperations",
            ),
            data=((100000, 95000), (120000, 110000)),
        ),
        retrieved_at=retrieved_at,
    )
    res = normalize_statement(raw)
    assert "NetIncomeFromContinuingOperationNetMinorityInterest" in res.table.index
    assert res.table.rows[0] == (100000.0, 95000.0)


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
