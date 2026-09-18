"""Typed provider-only failure abstraction.

This module defines provider error categories and representations.
Upper layers (domain, service, UI) consume these without importing yfinance.
"""

from __future__ import annotations

from enum import Enum


class ProviderFailureKind(str, Enum):
    """Categorized provider failure kinds."""

    RATE_LIMITED = "rate_limited"
    ACCESS_DENIED = "access_denied"
    UNAVAILABLE = "unavailable"
    BAD_RESPONSE = "bad_response"


class ProviderUpstreamError(Exception):
    """Typed provider failure representation.

    Ensures that raw response bodies, sensitive query parameters, cookies,
    and crumb tokens are never leaked past the provider boundary.
    """

    def __init__(
        self,
        kind: ProviderFailureKind,
        operation: str,
        http_status: int | None = None,
    ) -> None:
        self.kind = kind
        self.failure_kind = kind
        self.operation = operation
        self.http_status = http_status
        self.status_code = http_status
        msg = f"Provider failure ({kind.value}) during operation '{operation}'"
        if http_status is not None:
            msg += f" (HTTP {http_status})"
        super().__init__(msg)
