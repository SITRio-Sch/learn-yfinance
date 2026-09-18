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
from yf_learner.providers.errors import ProviderFailureKind, ProviderUpstreamError
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


def map_provider_error(err: ProviderUpstreamError) -> DataProblem:
    """Map typed provider upstream error to learner-friendly DataProblem with exact user-facing messages."""
    if err.kind == ProviderFailureKind.RATE_LIMITED:
        return DataProblem.create(
            ProblemKind.RATE_LIMITED,
            custom_message="Yahoo Finance rate-limited this app while fetching this data. No fallback data is shown.",
        )
    if err.kind == ProviderFailureKind.ACCESS_DENIED:
        return DataProblem.create(
            ProblemKind.ACCESS_DENIED,
            custom_message="Yahoo Finance rejected this app’s request while fetching this data. This does not mean the ticker lacks this data.",
        )
    if err.kind == ProviderFailureKind.UNAVAILABLE:
        return DataProblem.create(
            ProblemKind.UPSTREAM_UNAVAILABLE,
            custom_message="Yahoo Finance could not be reached successfully for this request. No fallback data is shown.",
        )
    if err.kind == ProviderFailureKind.BAD_RESPONSE:
        return DataProblem.create(
            ProblemKind.BAD_RESPONSE,
            custom_message="Yahoo Finance returned an unexpected response, so this data could not be displayed safely.",
        )
    return DataProblem.create(
        ProblemKind.UPSTREAM_UNAVAILABLE,
        custom_message="Yahoo Finance could not be reached successfully for this request. No fallback data is shown.",
    )


def map_exception_to_problem(exc: Exception) -> DataProblem:
    """Map provider or transport exceptions to learner-friendly DataProblem without tracebacks."""
    if isinstance(exc, ProviderUpstreamError):
        return map_provider_error(exc)

    msg = str(exc).lower()

    if "429" in msg or "rate limit" in msg or "too many requests" in msg:
        return DataProblem.create(ProblemKind.RATE_LIMITED)

    if isinstance(exc, TimeoutError) or "timeout" in msg or "timed out" in msg:
        return DataProblem.create(ProblemKind.TIMEOUT)

    if "401" in msg or "403" in msg or "crumb" in msg or "access denied" in msg or "unauthorized" in msg or "forbidden" in msg:
        return DataProblem.create(
            ProblemKind.ACCESS_DENIED,
            custom_message="Yahoo Finance rejected this app’s request while fetching this data. This does not mean the ticker lacks this data.",
        )

    if "404" in msg or "not found" in msg or "no data found" in msg:
        return DataProblem.create(ProblemKind.MISSING_DATA)

    if isinstance(exc, ValueError) or "invalid" in msg or "unsupported" in msg:
        return DataProblem.create(ProblemKind.INVALID_REQUEST)

    if "bad response" in msg:
        return DataProblem.create(
            ProblemKind.BAD_RESPONSE,
            custom_message="Yahoo Finance returned an unexpected response, so this data could not be displayed safely.",
        )

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
        except ProviderUpstreamError as pue:
            return DataResult.failure(map_provider_error(pue))
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

        try:
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
        except ProviderUpstreamError as pue:
            return DataResult.failure(map_provider_error(pue))
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

        try:
            snapshot = normalize_quote(raw)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

        # Verify that at least some key field is present
        if snapshot.last_price is None and snapshot.previous_close is None and snapshot.market_cap is None:
            return DataResult.failure(DataProblem.create(ProblemKind.MISSING_DATA))
        return DataResult.success(snapshot)

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
        except ProviderUpstreamError as pue:
            return DataResult.failure(map_provider_error(pue))
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

        try:
            result = normalize_history(raw)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

        if not result.points:
            return DataResult.failure(DataProblem.create(ProblemKind.MISSING_DATA))
        return DataResult.success(result)

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
        except ProviderUpstreamError as pue:
            return DataResult.failure(map_provider_error(pue))
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

        try:
            result = normalize_fundamentals(raw)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

        if result.name is None and result.market_cap is None and result.sector is None:
            return DataResult.failure(DataProblem.create(ProblemKind.MISSING_DATA))
        return DataResult.success(result)

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
        except ProviderUpstreamError as pue:
            return DataResult.failure(map_provider_error(pue))
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

        try:
            result = normalize_statement(raw)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

        if not result.table.columns or not result.table.index:
            return DataResult.failure(DataProblem.create(ProblemKind.MISSING_DATA))
        return DataResult.success(result)

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
        except ProviderUpstreamError as pue:
            return DataResult.failure(map_provider_error(pue))
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

        try:
            result = normalize_analyst(raw)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

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
        except ProviderUpstreamError as pue:
            return DataResult.failure(map_provider_error(pue))
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))

        try:
            result = normalize_news(raw)
            return DataResult.success(result)
        except Exception as exc:
            return DataResult.failure(map_exception_to_problem(exc))
