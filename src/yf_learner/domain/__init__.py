"""Domain models and errors for yf_learner."""

from yf_learner.domain.errors import (
    DataProblem,
    ProblemKind,
    STANDARD_PROBLEM_MESSAGES,
)
from yf_learner.domain.models import (
    AnalystPriceTargets,
    AnalystResult,
    DataResult,
    FundamentalsResult,
    HistoryPoint,
    HistoryResult,
    NewsItem,
    NewsResult,
    Provenance,
    QuoteSnapshot,
    SearchResultItem,
    SearchResults,
    StatementResult,
    TableData,
)

__all__ = [
    "DataProblem",
    "ProblemKind",
    "STANDARD_PROBLEM_MESSAGES",
    "Provenance",
    "DataResult",
    "SearchResultItem",
    "SearchResults",
    "QuoteSnapshot",
    "HistoryPoint",
    "HistoryResult",
    "FundamentalsResult",
    "TableData",
    "StatementResult",
    "AnalystPriceTargets",
    "AnalystResult",
    "NewsItem",
    "NewsResult",
]
