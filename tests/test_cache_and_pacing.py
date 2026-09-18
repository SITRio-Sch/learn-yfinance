"""Unit tests verifying caching behavior, refresh tokens, and RequestGate pacing."""

from __future__ import annotations

import threading
import time

import pytest
from streamlit.testing.v1 import AppTest

from tests.fakes import FakeMarketDataProvider
from yf_learner.domain.errors import ProblemKind
from yf_learner.services.market_data import MarketDataService
from yf_learner.services.request_gate import RequestGate
from yf_learner.ui.cache import set_service_override


def test_request_gate_pacing():
    simulated_time = [100.0]
    sleeps: list[float] = []

    def mock_clock() -> float:
        return simulated_time[0]

    def mock_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        simulated_time[0] += seconds

    gate = RequestGate(
        min_interval_seconds=0.25,
        clock=mock_clock,
        sleep_func=mock_sleep,
    )

    # First call: no sleep needed
    res1 = gate.execute(lambda: "call1")
    assert res1 == "call1"
    assert len(sleeps) == 0

    # Second call immediately after (elapsed 0.0s < 0.25s)
    res2 = gate.execute(lambda: "call2")
    assert res2 == "call2"
    assert len(sleeps) == 1
    assert pytest.approx(sleeps[0], 0.001) == 0.25


def test_request_gate_thread_safety():
    call_order: list[int] = []
    gate = RequestGate(min_interval_seconds=0.01)

    def worker(worker_id: int):
        gate.execute(lambda: call_order.append(worker_id))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(call_order) == 10


def test_caching_and_refresh_token_behavior():
    fake = FakeMarketDataProvider()
    fast_gate = RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None)
    service = MarketDataService(fake, gate=fast_gate)
    set_service_override(service)

    def cache_runner():
        import streamlit as st
        from yf_learner.ui.cache import cached_quote

        tok = st.session_state.get("refresh_token", 0)
        res = cached_quote("AAPL", token=tok)
        if res.is_success and res.value:
            st.write(f"price={res.value.last_price}")
        elif res.problem:
            st.error(res.problem.message)

    at = AppTest.from_function(cache_runner).run()

    # 1. First call with token=0
    assert fake.call_counts["quote"] == 1
    assert len(at.error) == 0

    # 2. Identical request with token=0 must be retrieved from cache
    at.run()
    assert fake.call_counts["quote"] == 1

    # 3. Increment token to 1: must trigger a new fetch
    at.session_state["refresh_token"] = 1
    at.run()
    assert fake.call_counts["quote"] == 2

    # 4. Failed refreshed request does not return previous success
    fake.error_to_raise = Exception("429 Too Many Requests")
    at.session_state["refresh_token"] = 2
    at.run()
    assert fake.call_counts["quote"] == 3
    # Error message must be rendered, and prior success value is removed
    assert any("limiting requests right now" in err.value for err in at.error)
    assert not any("price=" in m.value for m in at.markdown)
