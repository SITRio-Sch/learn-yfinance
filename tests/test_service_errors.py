"""Unit tests for service error handling and mapping to learner-friendly problems."""

from __future__ import annotations

import pytest

from tests.fakes import FakeMarketDataProvider
from yf_learner.domain.errors import ProblemKind
from yf_learner.providers.errors import ProviderFailureKind, ProviderUpstreamError
from yf_learner.services.market_data import MarketDataService, map_exception_to_problem
from yf_learner.services.request_gate import RequestGate


def test_error_mapping_messages_and_kinds():
    # 1. Rate limited
    p1 = map_exception_to_problem(Exception("HTTP 429: Too Many Requests / Rate limit exceeded"))
    assert p1.kind == ProblemKind.RATE_LIMITED
    assert p1.message == "Yahoo Finance is limiting requests right now. Try again later."
    assert "Traceback" not in p1.message
    assert "http" not in p1.message.lower()

    # 2. Timeout
    p2 = map_exception_to_problem(TimeoutError("Request timed out after 30 seconds"))
    assert p2.kind == ProblemKind.TIMEOUT
    assert p2.message == "Yahoo Finance did not respond in time."

    # 3. Missing data
    p3 = map_exception_to_problem(Exception("404 Client Error: No data found for symbol"))
    assert p3.kind == ProblemKind.MISSING_DATA
    assert p3.message == "Yahoo Finance did not return this data for this ticker."

    # 4. Invalid request
    p4 = map_exception_to_problem(ValueError("Invalid argument specified"))
    assert p4.kind == ProblemKind.INVALID_REQUEST
    assert p4.message == "Yahoo Finance could not process that request."

    # 5. Unexpected shape / parsing
    p5 = map_exception_to_problem(KeyError("missing_key"))
    assert p5.kind == ProblemKind.UNEXPECTED_RESPONSE
    assert p5.message == "Yahoo Finance returned data in a format this lesson does not recognize."

    # 6. Generic upstream unavailable
    p6 = map_exception_to_problem(ConnectionError("Connection refused by peer"))
    assert p6.kind == ProblemKind.UPSTREAM_UNAVAILABLE
    assert p6.message == "Yahoo Finance is temporarily unavailable."


def test_service_returns_data_result_failures():
    fake = FakeMarketDataProvider()
    # Fast-clock request gate for instantaneous unit tests
    gate = RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None)
    service = MarketDataService(fake, gate=gate)

    # Empty symbol or invalid argument
    res_empty = service.quote("")
    assert not res_empty.is_success
    assert res_empty.problem is not None
    assert res_empty.problem.kind == ProblemKind.INVALID_REQUEST

    # Simulated provider rate limit
    fake.error_to_raise = Exception("429 Too Many Requests")
    res_rl = service.quote("AAPL")
    assert not res_rl.is_success
    assert res_rl.problem is not None
    assert res_rl.problem.kind == ProblemKind.RATE_LIMITED
    assert res_rl.problem.message == "Yahoo Finance is limiting requests right now. Try again later."
    assert res_rl.value is None

    # Simulated timeout on history
    fake.error_to_raise = TimeoutError("Connection timed out")
    res_timeout = service.history("AAPL")
    assert not res_timeout.is_success
    assert res_timeout.problem is not None
    assert res_timeout.problem.kind == ProblemKind.TIMEOUT
    assert res_timeout.problem.message == "Yahoo Finance did not respond in time."

    # Simulated upstream unavailable on statements
    fake.error_to_raise = Exception("503 Service Unavailable")
    res_503 = service.financial_statement("AAPL", "Income statement")
    assert not res_503.is_success
    assert res_503.problem is not None
    assert res_503.problem.kind == ProblemKind.UPSTREAM_UNAVAILABLE
    assert res_503.problem.message == "Yahoo Finance is temporarily unavailable."


@pytest.mark.parametrize(
    ("kind", "problem_kind", "message"),
    [
        (
            ProviderFailureKind.RATE_LIMITED,
            ProblemKind.RATE_LIMITED,
            "Yahoo Finance rate-limited this app while fetching this data. No fallback data is shown.",
        ),
        (
            ProviderFailureKind.ACCESS_DENIED,
            ProblemKind.ACCESS_DENIED,
            "Yahoo Finance rejected this app’s request while fetching this data. This does not mean the ticker lacks this data.",
        ),
        (
            ProviderFailureKind.UNAVAILABLE,
            ProblemKind.UPSTREAM_UNAVAILABLE,
            "Yahoo Finance could not be reached successfully for this request. No fallback data is shown.",
        ),
        (
            ProviderFailureKind.BAD_RESPONSE,
            ProblemKind.BAD_RESPONSE,
            "Yahoo Finance returned an unexpected response, so this data could not be displayed safely.",
        ),
    ],
)
def test_typed_provider_failures_map_without_raw_details(kind, problem_kind, message):
    fake = FakeMarketDataProvider()
    fake.error_by_method["fundamentals"] = ProviderUpstreamError(kind=kind, operation="fundamentals")
    service = MarketDataService(
        fake,
        gate=RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None),
    )

    result = service.fundamentals("AAPL")

    assert result.value is None
    assert result.problem is not None
    assert result.problem.kind == problem_kind
    assert result.problem.message == message
    assert result.problem.details is None
    assert "crumb" not in result.problem.message.lower()


def test_incidental_text_not_mapped_to_access_denied():
    """Verify incidental numeric text, crumb keywords, and blocked text never become ACCESS_DENIED."""
    cases = [
        ValueError("account 401k retirement plan"),
        ValueError("error 403 invalid input"),
        KeyError("crumb"),
        Exception("unrelated thread blocked on resource"),
        Exception("processed 503 rows successfully"),
    ]
    for exc in cases:
        problem = map_exception_to_problem(exc)
        assert problem.kind != ProblemKind.ACCESS_DENIED, f"Exception {exc!r} incorrectly mapped to ACCESS_DENIED"


def test_exact_typed_access_denied_maps_correctly():
    """Verify typed ProviderUpstreamError with ACCESS_DENIED maps to ProblemKind.ACCESS_DENIED with exact message."""
    typed_error = ProviderUpstreamError(
        kind=ProviderFailureKind.ACCESS_DENIED,
        operation="quote",
        http_status=403,
    )
    problem = map_exception_to_problem(typed_error)
    assert problem.kind == ProblemKind.ACCESS_DENIED
    assert problem.message == (
        "Yahoo Finance rejected this app’s request while fetching this data. "
        "This does not mean the ticker lacks this data."
    )
    assert problem.details is None
