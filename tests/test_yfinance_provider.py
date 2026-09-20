"""Unit tests verifying YFinanceProvider operations and parameters."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import yf_learner.providers.yfinance_provider as provider_mod
from yf_learner.providers.errors import ProviderFailureKind, ProviderUpstreamError
from yf_learner.providers.yfinance_provider import YFinanceProvider


def test_provider_retries_configured():
    # Assert retries configured to exactly 2
    assert provider_mod.yf.config.network.retries == 2


def test_provider_search_exact_args(monkeypatch):
    mock_search = MagicMock()
    mock_quotes = [{"symbol": f"S{i}"} for i in range(12)]
    mock_search.return_value.quotes = mock_quotes
    monkeypatch.setattr(provider_mod.yf, "Search", mock_search)

    provider = YFinanceProvider()
    res = provider.search("apple")

    # Verify exact kwargs
    mock_search.assert_called_once_with(
        "apple",
        max_results=8,
        news_count=0,
        lists_count=0,
        include_cb=False,
        include_nav_links=False,
        include_research=False,
        include_cultural_assets=False,
        recommended=0,
        raise_errors=True,
    )
    # Ensure capped at at most 8
    assert len(res.raw_quotes) == 8


def test_provider_quote(monkeypatch):
    mock_ticker_cls = MagicMock()
    mock_ticker = mock_ticker_cls.return_value
    mock_ticker.get_fast_info.return_value = {"last_price": 150.0, "currency": "USD"}
    mock_ticker.get_history_metadata.return_value = {"regularMarketTime": 1710000000}
    monkeypatch.setattr(provider_mod.yf, "Ticker", mock_ticker_cls)

    provider = YFinanceProvider()
    res = provider.quote("AAPL")

    mock_ticker_cls.assert_called_once_with("AAPL")
    mock_ticker.get_fast_info.assert_called_once()
    mock_ticker.get_history_metadata.assert_called_once()
    assert res.fast_info["last_price"] == 150.0
    assert res.history_metadata["regularMarketTime"] == 1710000000


def test_provider_history_args(monkeypatch):
    mock_ticker_cls = MagicMock()
    mock_ticker = mock_ticker_cls.return_value
    mock_df = MagicMock()
    mock_df.empty = False
    mock_df.columns = ["Open", "Close"]
    mock_df.index = ["2026-01-01"]
    mock_df.itertuples.return_value = [(100.0, 105.0)]
    mock_ticker.history.return_value = mock_df
    monkeypatch.setattr(provider_mod.yf, "Ticker", mock_ticker_cls)

    provider = YFinanceProvider()
    res = provider.history("AAPL", period="6mo", interval="1wk", auto_adjust=True, actions=False)

    mock_ticker.history.assert_called_once_with(
        period="6mo",
        interval="1wk",
        auto_adjust=True,
        actions=False,
    )
    assert res.table.columns == ("Open", "Close")


def test_provider_statements_and_frequencies(monkeypatch):
    mock_ticker_cls = MagicMock()
    mock_ticker = mock_ticker_cls.return_value
    mock_df = MagicMock()
    mock_df.empty = True
    mock_ticker.get_income_stmt.return_value = mock_df
    mock_ticker.get_balance_sheet.return_value = mock_df
    mock_ticker.get_cash_flow.return_value = mock_df
    monkeypatch.setattr(provider_mod.yf, "Ticker", mock_ticker_cls)

    provider = YFinanceProvider()

    # Income statement yearly and quarterly
    provider.financial_statement("AAPL", "Income statement", "yearly")
    mock_ticker.get_income_stmt.assert_called_with(freq="yearly")

    provider.financial_statement("AAPL", "Income statement", "quarterly")
    mock_ticker.get_income_stmt.assert_called_with(freq="quarterly")

    # Balance sheet
    provider.financial_statement("AAPL", "Balance sheet", "yearly")
    mock_ticker.get_balance_sheet.assert_called_with(freq="yearly")

    # Cash flow
    provider.financial_statement("AAPL", "Cash flow", "yearly")
    mock_ticker.get_cash_flow.assert_called_with(freq="yearly")


def test_provider_analyst_methods(monkeypatch):
    mock_ticker_cls = MagicMock()
    mock_ticker = mock_ticker_cls.return_value
    mock_df = MagicMock()
    mock_df.empty = True
    mock_ticker.get_recommendations.return_value = mock_df
    mock_ticker.get_analyst_price_targets.return_value = {"current": 100.0}
    mock_ticker.get_earnings_estimate.return_value = mock_df
    mock_ticker.get_revenue_estimate.return_value = mock_df
    mock_ticker.get_growth_estimates.return_value = mock_df
    monkeypatch.setattr(provider_mod.yf, "Ticker", mock_ticker_cls)

    provider = YFinanceProvider()

    provider.analyst_data("AAPL", "recommendations")
    mock_ticker.get_recommendations.assert_called_once()

    provider.analyst_data("AAPL", "price_targets")
    mock_ticker.get_analyst_price_targets.assert_called_once()

    provider.analyst_data("AAPL", "earnings_estimate")
    mock_ticker.get_earnings_estimate.assert_called_once()

    provider.analyst_data("AAPL", "revenue_estimate")
    mock_ticker.get_revenue_estimate.assert_called_once()

    provider.analyst_data("AAPL", "growth_estimates")
    mock_ticker.get_growth_estimates.assert_called_once()


def test_provider_classifies_rate_limit_and_does_not_call_analyst_fallbacks(monkeypatch):
    mock_ticker_cls = MagicMock()
    mock_ticker = mock_ticker_cls.return_value
    mock_ticker.get_recommendations.side_effect = provider_mod.yf.exceptions.YFRateLimitError()
    monkeypatch.setattr(provider_mod.yf, "Ticker", mock_ticker_cls)

    with pytest.raises(ProviderUpstreamError) as raised:
        YFinanceProvider().analyst_data("AAPL", "recommendations")

    assert raised.value.kind == ProviderFailureKind.RATE_LIMITED
    mock_ticker.get_recommendations.assert_called_once()
    mock_ticker.get_analyst_price_targets.assert_not_called()
    mock_ticker.get_earnings_estimate.assert_not_called()
    mock_ticker.get_revenue_estimate.assert_not_called()
    mock_ticker.get_growth_estimates.assert_not_called()


@pytest.mark.parametrize(
    ("exception", "expected_kind"),
    [
        (RuntimeError("HTTP Error 401: Invalid Crumb"), ProviderFailureKind.ACCESS_DENIED),
        (RuntimeError("User is unable to access this feature"), ProviderFailureKind.ACCESS_DENIED),
        (RuntimeError("HTTP Error 403: Forbidden"), ProviderFailureKind.ACCESS_DENIED),
        (TimeoutError("request timed out"), ProviderFailureKind.UNAVAILABLE),
        (ConnectionError("connection refused"), ProviderFailureKind.UNAVAILABLE),
        (RuntimeError("HTTP Error 503: Service Unavailable"), ProviderFailureKind.UNAVAILABLE),
    ],
)
def test_provider_classifies_known_fundamentals_failures(monkeypatch, exception, expected_kind):
    mock_ticker_cls = MagicMock()
    mock_ticker_cls.return_value.get_info.side_effect = exception
    monkeypatch.setattr(provider_mod.yf, "Ticker", mock_ticker_cls)

    with pytest.raises(ProviderUpstreamError) as raised:
        YFinanceProvider().fundamentals("AAPL")

    assert raised.value.kind == expected_kind
    assert raised.value.operation == "fundamentals"
    assert "crumb" not in str(raised.value).lower()


@pytest.mark.parametrize(
    "exception",
    [
        RuntimeError("Invalid Crumb"),
        RuntimeError("  invalid \t crumb \n "),
        RuntimeError("USER IS UNABLE TO ACCESS THIS FEATURE"),
        RuntimeError("  User  is   unable to access this feature  "),
        RuntimeError("unable-to-access-feature"),
        RuntimeError("  UNABLE-TO-ACCESS-FEATURE \n "),
        RuntimeError("HTTP 401"),
        RuntimeError("HTTP 403"),
        type("StructuredStatus", (Exception,), {"status_code": 401})("auth required"),
        type("StructuredResponseStatus", (Exception,), {"response": type("Resp", (), {"status_code": 403})()})(
            "forbidden"
        ),
    ],
)
def test_provider_canonical_access_denied_phrases_and_statuses(monkeypatch, exception):
    mock_ticker_cls = MagicMock()
    mock_ticker_cls.return_value.get_info.side_effect = exception
    monkeypatch.setattr(provider_mod.yf, "Ticker", mock_ticker_cls)

    with pytest.raises(ProviderUpstreamError) as raised:
        YFinanceProvider().fundamentals("AAPL")

    assert raised.value.kind == ProviderFailureKind.ACCESS_DENIED
    assert raised.value.operation == "fundamentals"
    assert "crumb" not in str(raised.value).lower()


@pytest.mark.parametrize(
    "exception",
    [
        RuntimeError("diagnostic note mentioned invalid crumb previously"),
        RuntimeError("not an invalid crumb response"),
        RuntimeError("embedded unable-to-access-feature phrases in error"),
        RuntimeError("401 occurred previously"),
        RuntimeError("403 rows were rejected by validation"),
    ],
)
def test_provider_incidental_text_not_mapped_to_access_denied(monkeypatch, exception):
    assert provider_mod._classify_yfinance_exception(exception) != ProviderFailureKind.ACCESS_DENIED

    mock_ticker_cls = MagicMock()
    mock_ticker_cls.return_value.get_info.side_effect = exception
    monkeypatch.setattr(provider_mod.yf, "Ticker", mock_ticker_cls)

    with pytest.raises(RuntimeError) as raised:
        YFinanceProvider().fundamentals("AAPL")

    assert raised.value is exception


@pytest.mark.parametrize(
    ("exception", "expected_kind"),
    [
        (RuntimeError("HTTP 429"), ProviderFailureKind.RATE_LIMITED),
        (RuntimeError("HTTP Error 429"), ProviderFailureKind.RATE_LIMITED),
        (RuntimeError("HTTP 429: Too Many Requests"), ProviderFailureKind.RATE_LIMITED),
        (RuntimeError("HTTP 500"), ProviderFailureKind.UNAVAILABLE),
        (RuntimeError("HTTP Error 500: Internal Server Error"), ProviderFailureKind.UNAVAILABLE),
        (RuntimeError("HTTP 502: Bad Gateway"), ProviderFailureKind.UNAVAILABLE),
        (RuntimeError("HTTP Error 503: Service Unavailable"), ProviderFailureKind.UNAVAILABLE),
        (RuntimeError("HTTP 504: Gateway Timeout"), ProviderFailureKind.UNAVAILABLE),
    ],
)
def test_provider_explicit_text_statuses_classification(monkeypatch, exception, expected_kind):
    mock_ticker_cls = MagicMock()
    mock_ticker_cls.return_value.get_info.side_effect = exception
    monkeypatch.setattr(provider_mod.yf, "Ticker", mock_ticker_cls)

    with pytest.raises(ProviderUpstreamError) as raised:
        YFinanceProvider().fundamentals("AAPL")

    assert raised.value.kind == expected_kind
    assert raised.value.operation == "fundamentals"


def test_provider_rejects_unsupported_successful_shapes(monkeypatch):
    mock_ticker_cls = MagicMock()
    mock_ticker = mock_ticker_cls.return_value
    mock_ticker.get_info.return_value = []
    monkeypatch.setattr(provider_mod.yf, "Ticker", mock_ticker_cls)

    with pytest.raises(ProviderUpstreamError) as raised:
        YFinanceProvider().fundamentals("AAPL")

    assert raised.value.kind == ProviderFailureKind.BAD_RESPONSE


def test_provider_preserves_empty_supported_responses(monkeypatch):
    mock_ticker_cls = MagicMock()
    mock_ticker = mock_ticker_cls.return_value
    mock_ticker.get_info.return_value = {}
    mock_ticker.get_recommendations.return_value = type(
        "EmptyFrame", (), {"empty": True, "columns": (), "index": ()}
    )()
    mock_ticker.get_analyst_price_targets.return_value = {}
    monkeypatch.setattr(provider_mod.yf, "Ticker", mock_ticker_cls)

    fundamentals = YFinanceProvider().fundamentals("AAPL")
    recommendations = YFinanceProvider().analyst_data("AAPL", "recommendations")
    targets = YFinanceProvider().analyst_data("AAPL", "price_targets")

    assert fundamentals.info == {}
    assert recommendations.table is not None
    assert recommendations.table.columns == ()
    assert targets.targets_dict == {}


def test_provider_news_feed_tabs(monkeypatch):
    mock_ticker_cls = MagicMock()
    mock_ticker = mock_ticker_cls.return_value
    mock_ticker.get_news.return_value = []
    monkeypatch.setattr(provider_mod.yf, "Ticker", mock_ticker_cls)

    provider = YFinanceProvider()

    # 1. news
    provider.news("AAPL", feed="news", count=5)
    mock_ticker.get_news.assert_called_with(count=5, tab="news")

    # 2. all
    provider.news("AAPL", feed="all", count=10)
    mock_ticker.get_news.assert_called_with(count=10, tab="all")

    # 3. press releases (must be exact string with space)
    provider.news("AAPL", feed="press releases", count=8)
    mock_ticker.get_news.assert_called_with(count=8, tab="press releases")
