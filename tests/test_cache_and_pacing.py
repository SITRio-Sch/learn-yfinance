"""Unit tests verifying caching behavior, refresh tokens, and RequestGate pacing."""

from __future__ import annotations

import threading
import time

import pytest
from streamlit.testing.v1 import AppTest

from tests.fakes import FakeMarketDataProvider
from yf_learner.domain.errors import ProblemKind
from yf_learner.providers.errors import ProviderFailureKind, ProviderUpstreamError
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


def test_cached_fundamentals_schema_version_key():
    """Verify that fundamentals cache function includes non-underscore schema version in its signature."""
    import inspect
    from yf_learner.services.normalizers import FUNDAMENTALS_NORMALIZATION_SCHEMA_VERSION
    from yf_learner.ui.cache import _cached_fundamentals_versioned, cached_fundamentals

    # Verify constant is defined
    assert isinstance(FUNDAMENTALS_NORMALIZATION_SCHEMA_VERSION, int)

    # Inspect _cached_fundamentals_versioned parameters
    sig = inspect.signature(_cached_fundamentals_versioned)
    assert "normalization_schema_version" in sig.parameters
    # Streamlit cache keys exclude parameters with leading underscores; ensure none have leading underscores
    for param_name in sig.parameters:
        assert not param_name.startswith("_"), f"Parameter {param_name} starts with underscore and would be excluded from cache key"

    # The default is a stable session token; explicit refreshes replace it with a UUID.
    public_sig = inspect.signature(cached_fundamentals)
    assert "symbol" in public_sig.parameters
    assert "token" in public_sig.parameters
    assert public_sig.parameters["token"].default == "default"


def test_cached_fundamentals_versioning_and_invalidation():
    """Verify that fundamentals caching uses schema version and refresh token in cache keys."""
    fake = FakeMarketDataProvider()
    fast_gate = RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None)
    service = MarketDataService(fake, gate=fast_gate)
    set_service_override(service)

    def fundamentals_runner():
        import streamlit as st
        from yf_learner.ui.cache import _cached_fundamentals_versioned, cached_fundamentals

        tok = st.session_state.get("refresh_token", 0)
        custom_version = st.session_state.get("schema_version", None)

        if custom_version is not None:
            res = _cached_fundamentals_versioned("AAPL", normalization_schema_version=custom_version, token=tok)
        else:
            res = cached_fundamentals("AAPL", token=tok)

        if res.is_success and res.value:
            st.write(f"symbol={res.value.symbol}")

    at = AppTest.from_function(fundamentals_runner).run()

    # 1. First fetch with cached_fundamentals
    assert fake.call_counts["fundamentals"] == 1

    # 2. Identical request with cached_fundamentals must be retrieved from cache
    at.run()
    assert fake.call_counts["fundamentals"] == 1

    # 3. Refresh token increment triggers new fetch
    at.session_state["refresh_token"] = 1
    at.run()
    assert fake.call_counts["fundamentals"] == 2

    # 4. Modifying schema version changes cache key and triggers new fetch
    at.session_state["schema_version"] = 9999
    at.run()
    assert fake.call_counts["fundamentals"] == 3


def test_failed_fundamentals_refresh_is_cached_without_stale_success():
    """A failed refresh replaces the visible result and is not retried on the same token."""
    fake = FakeMarketDataProvider()
    service = MarketDataService(fake, gate=RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None))
    set_service_override(service)

    def fundamentals_runner():
        import streamlit as st
        from yf_learner.ui.cache import cached_fundamentals

        token = st.session_state.get("recovery_token", "default")
        result = cached_fundamentals("RECOVERY_FUNDAMENTALS", token=token)
        if result.problem is not None:
            st.error(result.problem.message)
        elif result.value is not None:
            st.write(f"name={result.value.name}")

    at = AppTest.from_function(fundamentals_runner).run()
    assert fake.call_counts["fundamentals"] == 1
    assert any("name=Apple Inc." in item.value for item in at.markdown)

    fake.error_to_raise = Exception("HTTP 429 Too Many Requests")
    at.session_state["recovery_token"] = "refresh-1"
    at.run()
    assert fake.call_counts["fundamentals"] == 2
    assert any("limiting requests right now" in item.value for item in at.error)
    assert not any("name=Apple Inc." in item.value for item in at.markdown)

    at.run()
    assert fake.call_counts["fundamentals"] == 2

    fake.error_to_raise = None
    at.session_state["recovery_token"] = "refresh-2"
    at.run()
    assert fake.call_counts["fundamentals"] == 3
    assert any("name=Apple Inc." in item.value for item in at.markdown)


def test_failed_analyst_refresh_is_cached_without_stale_success():
    """Analyst failures follow the same token-scoped recovery behavior as fundamentals."""
    fake = FakeMarketDataProvider()
    service = MarketDataService(fake, gate=RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None))
    set_service_override(service)

    def analyst_runner():
        import streamlit as st
        from yf_learner.ui.cache import cached_analyst

        token = st.session_state.get("analyst_recovery_token", "default")
        result = cached_analyst("RECOVERY_ANALYST", dataset="recommendations", token=token)
        if result.problem is not None:
            st.error(result.problem.message)
        elif result.value is not None:
            st.write("analyst-data-loaded")

    at = AppTest.from_function(analyst_runner).run()
    assert fake.call_counts["analyst_data"] == 1
    assert any("analyst-data-loaded" in item.value for item in at.markdown)

    fake.error_to_raise = ProviderUpstreamError(
        kind=ProviderFailureKind.ACCESS_DENIED,
        operation="analyst_data",
    )
    at.session_state["analyst_recovery_token"] = "refresh-1"
    at.run()
    assert fake.call_counts["analyst_data"] == 2
    assert any("limiting" not in item.value and "rejected this app" in item.value for item in at.error)
    assert not any("analyst-data-loaded" in item.value for item in at.markdown)

    at.run()
    assert fake.call_counts["analyst_data"] == 2


def test_cached_fundamentals_dividend_yield_end_to_end():
    """Verify that cached_fundamentals converts fake info dividendYield to canonical ratio and format_percent formats correctly."""
    from datetime import datetime, timezone
    from yf_learner.providers.raw_models import RawFundamentalsData
    from yf_learner.ui.components import NOT_AVAILABLE, format_percent

    cases = [
        (0.32, 0.0032, "0.32%"),
        (0.55, 0.0055, "0.55%"),
        (2.5, 0.025, "2.50%"),
        (0.0, 0.0, "0.00%"),
        (None, None, NOT_AVAILABLE),
        (float("nan"), None, NOT_AVAILABLE),
        ("NaN", None, NOT_AVAILABLE),
        ("nan", None, NOT_AVAILABLE),
        ("None", None, NOT_AVAILABLE),
        ("null", None, NOT_AVAILABLE),
        ("invalid", None, NOT_AVAILABLE),
    ]

    for i, (raw_val, expected_ratio, expected_display) in enumerate(cases):
        fake = FakeMarketDataProvider()
        fake.fundamentals = lambda sym, rv=raw_val: RawFundamentalsData(
            symbol=sym,
            info={
                "shortName": "Test Co",
                "quoteType": "EQUITY",
                "dividendYield": rv,
                "marketCap": 1000000,
                "sector": "Tech",
            },
            retrieved_at=datetime.now(timezone.utc),
        )
        service = MarketDataService(fake, gate=RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None))
        set_service_override(service)

        sym = f"TST{i}"

        def runner():
            import streamlit as st
            from yf_learner.ui.cache import cached_fundamentals
            from yf_learner.ui.components import format_percent

            target_sym = st.session_state.get("target_sym", "AAPL")
            res = cached_fundamentals(target_sym, token=0)
            st.session_state["res"] = res
            if res.is_success and res.value:
                st.session_state["div_yield"] = res.value.dividend_yield
                st.session_state["formatted"] = format_percent(res.value.dividend_yield)

        at = AppTest.from_function(runner)
        at.session_state["target_sym"] = sym
        at.run()
        res = at.session_state["res"]
        assert res.is_success, f"Failed for raw dividendYield {raw_val!r}: {res.problem}"
        assert res.value is not None
        assert res.value.dividend_yield == expected_ratio, (
            f"Expected canonical ratio {expected_ratio} for raw {raw_val!r}, got {res.value.dividend_yield}"
        )
        assert format_percent(res.value.dividend_yield) == expected_display, (
            f"Expected display string {expected_display!r} for raw {raw_val!r}, got {format_percent(res.value.dividend_yield)!r}"
        )
        assert at.session_state.get("formatted") == expected_display
