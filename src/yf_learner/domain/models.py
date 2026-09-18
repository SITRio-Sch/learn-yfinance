"""Domain models representing normalized financial and educational data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Generic, TypeVar

from yf_learner.domain.errors import DataProblem

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Provenance:
    """Provenance tracking where, when, and as-of what time data was obtained."""

    source: str
    retrieved_at: datetime
    data_as_of: datetime | date | None = None


@dataclass(frozen=True, slots=True)
class DataResult(Generic[T]):
    """Standardized result wrapper containing either data or a problem description."""

    value: T | None = None
    problem: DataProblem | None = None

    @property
    def is_success(self) -> bool:
        return self.problem is None and self.value is not None

    @classmethod
    def success(cls, value: T) -> DataResult[T]:
        return cls(value=value, problem=None)

    @classmethod
    def failure(cls, problem: DataProblem) -> DataResult[T]:
        return cls(value=None, problem=problem)


@dataclass(frozen=True, slots=True)
class SearchResultItem:
    """Individual quote match from Yahoo Search."""

    symbol: str
    name: str | None = None
    exchange: str | None = None
    quote_type: str | None = None


@dataclass(frozen=True, slots=True)
class SearchResults:
    """A list of search items for a query (at most 8 items)."""

    query: str
    items: tuple[SearchResultItem, ...]
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class QuoteSnapshot:
    """Curated real-time/delayed market snapshot fields."""

    symbol: str
    last_price: float | None = None
    previous_close: float | None = None
    open_price: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    volume: int | None = None
    average_volume: int | None = None
    average_volume_10d: int | None = None
    currency: str | None = None
    exchange: str | None = None
    timezone: str | None = None
    market_cap: int | float | None = None
    provenance: Provenance | None = None


@dataclass(frozen=True, slots=True)
class HistoryPoint:
    """A single OHLCV record in historical prices."""

    date_or_time: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    dividends: float | None = None
    stock_splits: float | None = None


@dataclass(frozen=True, slots=True)
class HistoryResult:
    """Normalized historical prices series."""

    symbol: str
    period: str
    interval: str
    auto_adjust: bool
    actions: bool
    points: tuple[HistoryPoint, ...]
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class FundamentalsResult:
    """Curated company and valuation fields.

    Invariant:
        dividend_yield is represented as a canonical fractional ratio
        (e.g., 0.0032 for 0.32%, 0.025 for 2.5%). Raw Yahoo/yfinance
        info["dividendYield"] returns percentage points and is divided
        by 100 at normalization. Missing, NaN, or non-numeric values
        normalize to None.
    """

    symbol: str
    name: str | None = None
    quote_type: str | None = None
    exchange: str | None = None
    currency: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    website: str | None = None
    employees: int | None = None
    market_cap: int | float | None = None
    enterprise_value: int | float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    business_summary: str | None = None
    provenance: Provenance | None = None


@dataclass(frozen=True, slots=True)
class TableData:
    """A 2D matrix representing financial statements or tabular analyst data."""

    columns: tuple[str, ...]
    index: tuple[str, ...]
    rows: tuple[tuple[object | None, ...], ...]


@dataclass(frozen=True, slots=True)
class StatementResult:
    """Normalized balance sheet, income statement, or cash flow."""

    symbol: str
    statement_type: str  # e.g., "Income statement", "Balance sheet", "Cash flow"
    frequency: str  # "yearly" or "quarterly"
    table: TableData
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class AnalystPriceTargets:
    """Analyst price target estimates."""

    current: float | None = None
    low: float | None = None
    high: float | None = None
    mean: float | None = None
    median: float | None = None


@dataclass(frozen=True, slots=True)
class AnalystResult:
    """Normalized analyst dataset."""

    symbol: str
    dataset_type: str
    table: TableData | None = None
    targets: AnalystPriceTargets | None = None
    provenance: Provenance | None = None


@dataclass(frozen=True, slots=True)
class NewsItem:
    """A single news item article."""

    title: str
    publisher: str | None = None
    link: str | None = None
    published_at: datetime | None = None
    uuid: str | None = None


@dataclass(frozen=True, slots=True)
class NewsResult:
    """A list of news articles for a ticker."""

    symbol: str
    feed: str
    items: tuple[NewsItem, ...]
    provenance: Provenance
