"""UI AppTest tests for initial render, educational notice, and search flows."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from tests.fakes import FakeMarketDataProvider
from yf_learner.services.market_data import MarketDataService
from yf_learner.services.request_gate import RequestGate
from yf_learner.ui.cache import set_service_override

APP_PATH = str((Path(__file__).parent.parent / "app.py").resolve())


def _setup_apptest():
    fake = FakeMarketDataProvider()
    service = MarketDataService(
        fake,
        gate=RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None),
    )
    set_service_override(service)
    at = AppTest.from_file(APP_PATH, default_timeout=10)
    return at, fake


def test_initial_render_zero_provider_calls():
    at, fake = _setup_apptest()
    at.run()

    # Zero provider calls on initial render
    assert sum(fake.call_counts.values()) == 0

    # Notice and title visible
    assert any("Learn yFinance" in m.value for m in at.title)
    # Search input exists
    assert at.text_input(key="search_query_input") is not None


def test_search_typing_performs_no_calls():
    at, fake = _setup_apptest()
    at.run()

    # Type query without clicking submit
    at.text_input(key="search_query_input").input("AAPL").run()
    assert fake.call_counts["search"] == 0


def test_search_empty_query_validation():
    at, fake = _setup_apptest()
    at.run()

    # Submit empty string
    at.text_input(key="search_query_input").input("   ").run()
    at.button(key="FormSubmitter:search_form-Search").click().run()

    # Should not call provider and should display warning
    assert fake.call_counts["search"] == 0
    assert any("Please enter a non-empty search query" in w.value for w in at.warning)


def test_search_submit_and_selection_does_not_open_ticker():
    at, fake = _setup_apptest()
    at.run()

    # Enter valid query and submit
    at.text_input(key="search_query_input").input("AAPL").run()
    at.button(key="FormSubmitter:search_form-Search").click().run()

    # Exactly 1 search call
    assert fake.call_counts["search"] == 1
    # At most 8 results
    radio = at.radio(key="search_results_radio")
    assert radio is not None
    assert len(radio.options) <= 8

    # Zero quote or detail calls made yet
    assert fake.call_counts["quote"] == 0

    # Select an item in radio
    radio.set_value(radio.options[0]).run()
    # Still zero quote calls
    assert fake.call_counts["quote"] == 0


def test_open_ticker_explicit_button_required():
    at, fake = _setup_apptest()
    at.run()

    at.text_input(key="search_query_input").input("AAPL").run()
    at.button(key="FormSubmitter:search_form-Search").click().run()

    # Click Open ticker button
    assert at.button(key="open_ticker_btn") is not None
    at.button(key="open_ticker_btn").click().run()

    # Active ticker is set
    assert at.session_state.get("active_symbol") == "AAPL"
    # Persistent header and tabs rendered
    assert fake.call_counts["quote"] == 1
    # Hidden tabs were not loaded
    assert fake.call_counts["history"] == 0
    assert fake.call_counts["fundamentals"] == 0
    assert fake.call_counts["financial_statement"] == 0
    assert fake.call_counts["analyst_data"] == 0
    assert fake.call_counts["news"] == 0
