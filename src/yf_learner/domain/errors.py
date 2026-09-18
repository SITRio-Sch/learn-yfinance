"""Domain error definitions and problem representations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProblemKind(str, Enum):
    """Categorized problem kinds for user-friendly error messages."""

    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    MISSING_DATA = "missing_data"
    INVALID_REQUEST = "invalid_request"
    UNEXPECTED_RESPONSE = "unexpected_response"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    ACCESS_DENIED = "access_denied"
    BAD_RESPONSE = "bad_response"


STANDARD_PROBLEM_MESSAGES: dict[ProblemKind, str] = {
    ProblemKind.RATE_LIMITED: "Yahoo Finance is limiting requests right now. Try again later.",
    ProblemKind.TIMEOUT: "Yahoo Finance did not respond in time.",
    ProblemKind.MISSING_DATA: "Yahoo Finance did not return this data for this ticker.",
    ProblemKind.INVALID_REQUEST: "Yahoo Finance could not process that request.",
    ProblemKind.UNEXPECTED_RESPONSE: "Yahoo Finance returned data in a format this lesson does not recognize.",
    ProblemKind.UPSTREAM_UNAVAILABLE: "Yahoo Finance is temporarily unavailable.",
    ProblemKind.ACCESS_DENIED: "Yahoo Finance rejected this app’s request while fetching this data. This does not mean the ticker lacks this data.",
    ProblemKind.BAD_RESPONSE: "Yahoo Finance returned an unexpected response, so this data could not be displayed safely.",
}


@dataclass(frozen=True, slots=True)
class DataProblem:
    """Represents a friendly error or missing data problem without raw tracebacks."""

    kind: ProblemKind
    message: str
    details: str | None = None

    @classmethod
    def create(cls, kind: ProblemKind, custom_message: str | None = None, details: str | None = None) -> DataProblem:
        message = custom_message or STANDARD_PROBLEM_MESSAGES[kind]
        return cls(kind=kind, message=message, details=details)
