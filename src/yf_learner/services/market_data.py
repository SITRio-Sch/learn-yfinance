"""Market data service coordinating provider calls, pacing, and normalization."""

from __future__ import annotations

import logging
from typing import Any

from yf_learner.domain.errors import DataProblem, ProblemKind
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
from yf_learner.providers.protocol import MarketDataProvider
from yf_learner.services.normalizers import (
    normalize_analyst,
    normalize_fundamentals,
    normalize_history,
    normalize_news,
    normalize_quote,
    normalize_search,
    normalize_statement,
)
from yf_learner.services.request_gate import RequestGate

logger = logging.getLogger(__name__)


def map_exception_to_problem(exc: Exception) -> DataProblem:
    """Map provider or transport exceptions to learner-friendly DataProblem without tracebacks."""
    msg = str(exc).lower()

    if "429" in msg or "rate limit" in msg or "too many requests" in msg:
        return DataProblem.create(ProblemKind.RATE_LIMITED)

    if isinstance(exc, TimeoutError) or "timeout" in msg or "timed out" in msg:
        return DataProblem.create(ProblemKind.TIMEOUT)

    if "404" in msg or "not found" in msg or "no data found" in msg:
        return DataProblem.create(ProblemKind.MISSING_DATA)

    if isinstance(exc, ValueError) or "invalid" in msg or "unsupported" in msg:
        return DataProblem.create(ProblemKind.INVALID_REQUEST)

    if isinstance(exc, (KeyError, IndexError, TypeError, AttributeError)):
        return DataProblem.create(ProblemKind.UNEXPECTED_RESPONSE)

    if (
        "500" in msg
        or "502" in msg
        or "503" in msg
        or "504" in msg
        or "connection" in msg
        or "down" in msg
        or "unavailable" in msg
        or "socket" in msg
    ):
        return DataProblem.create(ProblemKind.UPSTREAM_UNAVAILABLE)

    # General upstream fallback
    return DataProblem.create(ProblemKind.UPSTREAM_UNAVAILABLE)


class MarketDataService:
    """Service facade for the UI to consume typed market data."""

    def __init__(
        self,
        provider: MarketDataProvider,
        gate: RequestGate | None = None,
    ) -> None:
        self._provider = provider
        self._gate = gate or RequestGate()

    def search(self, query: str) -> DataResult[SearchResults]:
        """Search Yahoo Finance quotes matching query."""
        trimmed = query.strip()
        if not trimmed:
            return DataResult.failure(
                DataProblem.create(
                    ProblemKind.INVALID_REQUEST,
                    custom_message="Search query cannot be empty.",
                )
            )

        try:
            raw = self._gate.execute(self._provider.search, trimmed)
            results = normalize_search(raw, trimmed)
            return DataResult.success(results)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

    def quote(self, symbol: str) -> DataResult[QuoteSnapshot]:
        """Fetch normalized quote snapshot for symbol."""
        trimmed = symbol.strip().upper()
        if not trimmed:
            return DataResult.failure(
                DataProblem.create(
                    ProblemKind.INVALID_REQUEST,
                    custom_message="Symbol cannot be empty.",
                )
            )

        try:
            raw = self._gate.execute(self._provider.quote, trimmed)
            snapshot = normalize_quote(raw)
            # Verify that at least some key field is present
            if snapshot.last_price is None and snapshot.previous_close is None and snapshot.market_cap is None:
                return DataResult.failure(DataProblem.create(ProblemKind.MISSING_DATA))
            return DataResult.success(snapshot)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

    def history(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
        auto_adjust: bool = True,
        actions: bool = False,
    ) -> DataResult[HistoryResult]:
        """Fetch historical price table for symbol."""
        trimmed = symbol.strip().upper()
        if not trimmed:
            return DataResult.failure(
                DataProblem.create(
                    ProblemKind.INVALID_REQUEST,
                    custom_message="Symbol cannot be empty.",
                )
            )

        # Validate allowed intervals and periods
        allowed_intervals = ("1d", "1wk", "1mo")
        allowed_periods = ("1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")

        if interval not in allowed_intervals:
            return DataResult.failure(
                DataProblem.create(
                    ProblemKind.INVALID_REQUEST,
                    custom_message=f"Interval '{interval}' is not supported. Choose from: {', '.join(allowed_intervals)}",
                )
            )

        if period not in allowed_periods:
            return DataResult.failure(
                DataProblem.create(
                    ProblemKind.INVALID_REQUEST,
                    custom_message=f"Period '{period}' is not supported. Choose from: {', '.join(allowed_periods)}",
                )
            )

        try:
            raw = self._gate.execute(
                self._provider.history,
                trimmed,
                period,
                interval,
                auto_adjust,
                actions,
            )
            result = normalize_history(raw)
            if not result.points:
                return DataResult.failure(DataProblem.create(ProblemKind.MISSING_DATA))
            return DataResult.success(result)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

    def fundamentals(self, symbol: str) -> DataResult[FundamentalsResult]:
        """Fetch company fundamentals for symbol."""
        trimmed = symbol.strip().upper()
        if not trimmed:
            return DataResult.failure(
                DataProblem.create(
                    ProblemKind.INVALID_REQUEST,
                    custom_message="Symbol cannot be empty.",
                )
            )

        try:
            raw = self._gate.execute(self._provider.fundamentals, trimmed)
            result = normalize_fundamentals(raw)
            if result.name is None and result.market_cap is None and result.sector is None:
                return DataResult.failure(DataProblem.create(ProblemKind.MISSING_DATA))
            return DataResult.success(result)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

    def financial_statement(
        self,
        symbol: str,
        statement: str,
        frequency: str = "yearly",
    ) -> DataResult[StatementResult]:
        """Fetch financial statement for symbol."""
        trimmed = symbol.strip().upper()
        if not trimmed:
            return DataResult.failure(
                DataProblem.create(
                    ProblemKind.INVALID_REQUEST,
                    custom_message="Symbol cannot be empty.",
                )
            )

        if frequency not in ("yearly", "quarterly"):
            return DataResult.failure(
                DataProblem.create(
                    ProblemKind.INVALID_REQUEST,
                    custom_message="Frequency must be 'yearly' or 'quarterly'.",
                )
            )

        try:
            raw = self._gate.execute(
                self._provider.financial_statement,
                trimmed,
                statement,
                frequency,
            )
            result = normalize_statement(raw)
            if not result.table.columns or not result.table.index:
                return DataResult.failure(DataProblem.create(ProblemKind.MISSING_DATA))
            return DataResult.success(result)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

    def analyst_data(
        self,
        symbol: str,
        dataset: str,
    ) -> DataResult[AnalystResult]:
        """Fetch analyst data (recommendations, targets, estimates) for symbol."""
        trimmed = symbol.strip().upper()
        if not trimmed:
            return DataResult.failure(
                DataProblem.create(
                    ProblemKind.INVALID_REQUEST,
                    custom_message="Symbol cannot be empty.",
                )
            )

        allowed_datasets = (
            "recommendations",
            "price_targets",
            "earnings_estimate",
            "revenue_estimate",
            "growth_estimates",
        )
        if dataset not in allowed_datasets:
            return DataResult.failure(
                DataProblem.create(
                    ProblemKind.INVALID_REQUEST,
                    custom_message=f"Dataset '{dataset}' is not supported. Choose from: {', '.join(allowed_datasets)}",
                )
            )

        try:
            raw = self._gate.execute(self._provider.analyst_data, trimmed, dataset)
            result = normalize_analyst(raw)
            if result.table is None and result.targets is None:
                return DataResult.failure(DataProblem.create(ProblemKind.MISSING_DATA))
            if result.table is not None and (not result.table.columns or not result.table.index):
                return DataResult.failure(DataProblem.create(ProblemKind.MISSING_DATA))
            if result.targets is not None and all(
                v is None for v in (
                    result.targets.current,
                    result.targets.low,
                    result.targets.high,
                    result.targets.mean,
                    result.targets.median,
                )
            ):
                return DataResult.failure(DataProblem.create(ProblemKind.MISSING_DATA))

            return DataResult.success(result)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

    def news(
        self,
        symbol: str,
        feed: str = "news",
        count: int = 8,
    ) -> DataResult[NewsResult]:
        """Fetch news articles for symbol."""
        trimmed = symbol.strip().upper()
        if not trimmed:
            return DataResult.failure(
                DataProblem.create(
                    ProblemKind.INVALID_REQUEST,
                    custom_message="Symbol cannot be empty.",
                )
            )

        allowed_feeds = ("news", "all", "press releases")
        if feed not in allowed_feeds:
            return DataResult.failure(
                DataProblem.create(
                    ProblemKind.INVALID_REQUEST,
                    custom_message=f"Feed '{feed}' is not supported. Choose from: {', '.join(allowed_feeds)}",
                )
            )

        try:
            raw = self._gate.execute(self._provider.news, trimmed, feed, count)
            result = normalize_news(raw)
            return DataResult.success(result)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))
