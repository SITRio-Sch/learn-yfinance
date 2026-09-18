"""Raw boundary models bridging the provider and normalizers.

Contains only plain Python primitives: tuples, dicts, lists, strings, numbers,
and datetimes without pandas or yfinance library types.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class RawTable:
    """Plain-object tabular data representation."""

    columns: tuple[str, ...]
    index: tuple[str, ...]
    data: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True, slots=True)
class RawSearchResults:
    """Raw quotes list from search operation."""

    raw_quotes: list[dict[str, Any]]
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class RawQuoteData:
    """Raw fast_info and history_metadata dictionaries."""

    symbol: str
    fast_info: dict[str, Any]
    history_metadata: dict[str, Any]
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class RawHistoryData:
    """Raw history table representation."""

    symbol: str
    period: str
    interval: str
    auto_adjust: bool
    actions: bool
    table: RawTable
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class RawFundamentalsData:
    """Raw info dictionary."""

    symbol: str
    info: dict[str, Any]
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class RawStatementData:
    """Raw statement table representation."""

    symbol: str
    statement: str
    frequency: str
    table: RawTable
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class RawAnalystData:
    """Raw analyst data representation (table or target price mapping)."""

    symbol: str
    dataset: str
    table: RawTable | None
    targets_dict: dict[str, Any] | None
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class RawNewsData:
    """Raw news articles list."""

    symbol: str
    feed: str
    raw_items: list[dict[str, Any]]
    retrieved_at: datetime
