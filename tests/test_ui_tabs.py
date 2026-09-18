"""UI AppTest tests verifying the six lazy tabs, teaching copy, code snippets, and provenance."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from tests.fakes import FakeMarketDataProvider
from yf_learner.services.market_data import MarketDataService
from yf_learner.services.request_gate import RequestGate
from yf_learner.ui.cache import set_service_override

APP_PATH = str((Path(__file__).parent.parent / "app.py").resolve())


def _setup_open_ticker_app():
    fake = FakeMarketDataProvider()
    service = MarketDataService(
        fake,
        gate=RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None),
    )
    set_service_override(service)
    at = AppTest.from_file(APP_PATH, default_timeout=10)
    at.run()
    at.text_input(key="search_query_input").input("AAPL").run()
    at.button(key="FormSubmitter:search_form-Search").click().run()
    at.button(key="open_ticker_btn").click().run()
    return at, fake


def test_exactly_six_tabs_exposed():
    at, fake = _setup_open_ticker_app()
    assert len(at.tabs) == 6
    expected_tabs = [
        "Quote",
        "History",
        "Fundamentals",
        "Financial Statements",
        "Analyst Data",
        "News",
    ]
    # Check tab labels
    for idx, expected in enumerate(expected_tabs):
        assert at.tabs[idx].label == expected


def test_lazy_tab_switching_fetches_only_active_tab():
    at, fake = _setup_open_ticker_app()

    # On open, Quote is active, so only quote has been called once
    assert fake.call_counts["quote"] == 1
    assert fake.call_counts["history"] == 0
    assert fake.call_counts["fundamentals"] == 0
    assert fake.call_counts["financial_statement"] == 0
    assert fake.call_counts["analyst_data"] == 0
    assert fake.call_counts["news"] == 0

    # Switch to History
    at.session_state["learning_tab"] = "History"
    at.run()
    assert fake.call_counts["history"] == 1
    assert fake.call_counts["fundamentals"] == 0

    # Switch to Fundamentals
    at.session_state["learning_tab"] = "Fundamentals"
    at.run()
    assert fake.call_counts["fundamentals"] == 1
    assert fake.call_counts["financial_statement"] == 0

    # Switch to Financial Statements
    at.session_state["learning_tab"] = "Financial Statements"
    at.run()
    assert fake.call_counts["financial_statement"] == 1
    assert fake.call_counts["analyst_data"] == 0

    # Switch to Analyst Data
    at.session_state["learning_tab"] = "Analyst Data"
    at.run()
    assert fake.call_counts["analyst_data"] == 1
    assert fake.call_counts["news"] == 0

    # Switch to News
    at.session_state["learning_tab"] = "News"
    at.run()
    assert fake.call_counts["news"] == 1


def test_each_tab_includes_teaching_snippet_refresh_provenance():
    at, fake = _setup_open_ticker_app()

    # 1. Quote tab elements
    assert any("Quote Snapshot" in s.value for s in at.subheader)
    assert any("What yfinance is doing" in exp.label for exp in at.expander)
    assert at.button(key="btn_refresh_quote") is not None
    assert any("Source: `Yahoo Finance via yfinance`" in m.value for m in at.markdown)

    # 2. History tab
    at.session_state["learning_tab"] = "History"
    at.run()
    assert any("Historical Prices" in s.value for s in at.subheader)
    assert at.button(key="btn_refresh_history") is not None
    assert any("What yfinance is doing" in exp.label for exp in at.expander)
    assert any("Source: `Yahoo Finance via yfinance`" in m.value for m in at.markdown)

    # 3. Fundamentals tab
    at.session_state["learning_tab"] = "Fundamentals"
    at.run()
    assert any("Company Fundamentals" in s.value for s in at.subheader)
    assert at.button(key="btn_refresh_fundamentals") is not None
    assert any("What yfinance is doing" in exp.label for exp in at.expander)
    assert any("Source: `Yahoo Finance via yfinance`" in m.value for m in at.markdown)

    # 4. Financial Statements tab
    at.session_state["learning_tab"] = "Financial Statements"
    at.run()
    assert any("Financial Statements" in s.value for s in at.subheader)
    assert at.button(key="btn_refresh_statements") is not None
    assert any("What yfinance is doing" in exp.label for exp in at.expander)
    assert any("Source: `Yahoo Finance via yfinance`" in m.value for m in at.markdown)

    # 5. Analyst Data tab
    at.session_state["learning_tab"] = "Analyst Data"
    at.run()
    assert any("Analyst Data" in s.value for s in at.subheader)
    assert at.button(key="btn_refresh_analyst") is not None
    assert any("What yfinance is doing" in exp.label for exp in at.expander)
    assert any("Source: `Yahoo Finance via yfinance`" in m.value for m in at.markdown)

    # 6. News tab
    at.session_state["learning_tab"] = "News"
    at.run()
    assert any("News" in s.value for s in at.subheader)
    assert at.button(key="btn_refresh_news") is not None
    assert any("What yfinance is doing" in exp.label for exp in at.expander)
    assert any("Source: `Yahoo Finance via yfinance`" in m.value for m in at.markdown)
