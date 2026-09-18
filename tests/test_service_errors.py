"""Unit tests for service error handling and mapping to learner-friendly problems."""

from __future__ import annotations

import pytest

from tests.fakes import FakeMarketDataProvider
from yf_learner.domain.errors import ProblemKind
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
