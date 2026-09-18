"""Unit tests verifying YFinanceProvider operations and parameters."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import yf_learner.providers.yfinance_provider as provider_mod
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
