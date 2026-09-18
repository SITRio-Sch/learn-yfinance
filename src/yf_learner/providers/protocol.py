"""Market data provider protocol definition."""

from __future__ import annotations

from typing import Protocol

from yf_learner.providers.raw_models import (
    RawAnalystData,
    RawFundamentalsData,
    RawHistoryData,
    RawNewsData,
    RawQuoteData,
    RawSearchResults,
    RawStatementData,
)


class MarketDataProvider(Protocol):
    """Protocol defining the explicit market data provider contract."""

    def search(self, query: str) -> RawSearchResults:
        """Search for quotes matching the query."""
        ...

    def quote(self, symbol: str) -> RawQuoteData:
        """Retrieve real-time/delayed fast_info and history_metadata for symbol."""
        ...

    def history(
        self,
        symbol: str,
        period: str,
        interval: str,
        auto_adjust: bool,
        actions: bool,
    ) -> RawHistoryData:
        """Retrieve historical price/action data for symbol."""
        ...

    def fundamentals(self, symbol: str) -> RawFundamentalsData:
        """Retrieve company and valuation fundamental info for symbol."""
        ...

    def financial_statement(
        self,
        symbol: str,
        statement: str,
        frequency: str,
    ) -> RawStatementData:
        """Retrieve financial statement data (income stmt, balance sheet, or cash flow)."""
        ...

    def analyst_data(self, symbol: str, dataset: str) -> RawAnalystData:
        """Retrieve analyst recommendations, targets, or estimates."""
        ...

    def news(self, symbol: str, feed: str, count: int) -> RawNewsData:
        """Retrieve news articles for symbol."""
        ...
