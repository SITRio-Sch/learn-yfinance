"""In-memory fake provider for automated unit and UI testing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from yf_learner.providers.protocol import MarketDataProvider
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


class FakeMarketDataProvider(MarketDataProvider):
    """Controllable fake provider implementing MarketDataProvider protocol without network."""

    def __init__(self) -> None:
        self.call_counts: dict[str, int] = {
            "search": 0,
            "quote": 0,
            "history": 0,
            "fundamentals": 0,
            "financial_statement": 0,
            "analyst_data": 0,
            "news": 0,
        }
        self.error_to_raise: Exception | None = None
        self.error_by_method: dict[str, Exception] = {}

        # Default sample payloads
        self.sample_search_quotes: list[dict[str, Any]] = [
            {
                "symbol": "AAPL",
                "shortname": "Apple Inc.",
                "exchange": "NMS",
                "quoteType": "EQUITY",
            },
            {
                "symbol": "MSFT",
                "shortname": "Microsoft Corporation",
                "exchange": "NMS",
                "quoteType": "EQUITY",
            },
        ]
        self.sample_fast_info: dict[str, Any] = {
            "last_price": 185.50,
            "previous_close": 184.20,
            "open": 184.90,
            "day_high": 186.20,
            "day_low": 184.50,
            "year_high": 199.62,
            "year_low": 164.08,
            "last_volume": 48_500_000,
            "three_month_average_volume": 52_000_000,
            "ten_day_average_volume": 49_100_000,
            "currency": "USD",
            "exchange": "NASDAQ",
            "timezone": "America/New_York",
            "market_cap": 2_850_000_000_000,
        }
        self.sample_metadata: dict[str, Any] = {
            "regularMarketTime": 1710000000,
            "currency": "USD",
            "exchangeName": "NASDAQ",
        }

    def _check_error(self, method: str) -> None:
        if self.error_to_raise is not None:
            raise self.error_to_raise
        if method in self.error_by_method:
            raise self.error_by_method[method]

    def search(self, query: str) -> RawSearchResults:
        self.call_counts["search"] += 1
        self._check_error("search")
        return RawSearchResults(
            raw_quotes=list(self.sample_search_quotes),
            retrieved_at=datetime.now(timezone.utc),
        )

    def quote(self, symbol: str) -> RawQuoteData:
        self.call_counts["quote"] += 1
        self._check_error("quote")
        return RawQuoteData(
            symbol=symbol,
            fast_info=dict(self.sample_fast_info),
            history_metadata=dict(self.sample_metadata),
            retrieved_at=datetime.now(timezone.utc),
        )

    def history(
        self,
        symbol: str,
        period: str,
        interval: str,
        auto_adjust: bool,
        actions: bool,
    ) -> RawHistoryData:
        self.call_counts["history"] += 1
        self._check_error("history")
        table = RawTable(
            columns=("Open", "High", "Low", "Close", "Volume"),
            index=("2026-03-01", "2026-03-02"),
            data=(
                (180.0, 182.0, 179.5, 181.5, 50000000),
                (181.5, 185.0, 181.0, 184.0, 52000000),
            ),
        )
        return RawHistoryData(
            symbol=symbol,
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            actions=actions,
            table=table,
            retrieved_at=datetime.now(timezone.utc),
        )

    def fundamentals(self, symbol: str) -> RawFundamentalsData:
        self.call_counts["fundamentals"] += 1
        self._check_error("fundamentals")
        info = {
            "shortName": "Apple Inc.",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "currency": "USD",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "United States",
            "website": "https://www.apple.com",
            "fullTimeEmployees": 161000,
            "marketCap": 2850000000000,
            "enterpriseValue": 2900000000000,
            "trailingPE": 30.5,
            "forwardPE": 28.2,
            "priceToBook": 45.1,
            "dividendYield": 0.0055,
            "beta": 1.25,
            "longBusinessSummary": "Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories.",
        }
        return RawFundamentalsData(
            symbol=symbol,
            info=info,
            retrieved_at=datetime.now(timezone.utc),
        )

    def financial_statement(
        self,
        symbol: str,
        statement: str,
        frequency: str,
    ) -> RawStatementData:
        self.call_counts["financial_statement"] += 1
        self._check_error("financial_statement")
        table = RawTable(
            columns=("2025-09-30", "2024-09-30"),
            index=("Total Revenue", "Operating Income", "Net Income"),
            data=(
                (390000000000, 380000000000),
                (120000000000, 115000000000),
                (100000000000, 97000000000),
            ),
        )
        return RawStatementData(
            symbol=symbol,
            statement=statement,
            frequency=frequency,
            table=table,
            retrieved_at=datetime.now(timezone.utc),
        )

    def analyst_data(self, symbol: str, dataset: str) -> RawAnalystData:
        self.call_counts["analyst_data"] += 1
        self._check_error("analyst_data")
        if dataset == "price_targets":
            return RawAnalystData(
                symbol=symbol,
                dataset=dataset,
                table=None,
                targets_dict={
                    "current": 185.50,
                    "low": 160.0,
                    "high": 240.0,
                    "mean": 205.0,
                    "median": 200.0,
                },
                retrieved_at=datetime.now(timezone.utc),
            )

        table = RawTable(
            columns=("strongBuy", "buy", "hold", "sell", "strongSell"),
            index=("0m", "-1m"),
            data=((10, 20, 8, 2, 0), (11, 19, 8, 2, 0)),
        )
        return RawAnalystData(
            symbol=symbol,
            dataset=dataset,
            table=table,
            targets_dict=None,
            retrieved_at=datetime.now(timezone.utc),
        )

    def news(self, symbol: str, feed: str, count: int) -> RawNewsData:
        self.call_counts["news"] += 1
        self._check_error("news")
        items = [
            {
                "title": "Apple Unveils New Product Line",
                "publisher": "Tech Daily",
                "link": "https://example.com/news/1",
                "providerPublishTime": 1710010000,
                "uuid": "news-uuid-1",
            }
        ]
        return RawNewsData(
            symbol=symbol,
            feed=feed,
            raw_items=items[:count],
            retrieved_at=datetime.now(timezone.utc),
        )
