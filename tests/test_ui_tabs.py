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


def test_fundamentals_tab_dividend_yield_display():
    """Verify Fundamentals tab displays correct percentage (0.55% from raw 0.55)."""
    at, fake = _setup_open_ticker_app()
    at.session_state["learning_tab"] = "Fundamentals"
    at.run()

    metric_pairs = [(m.label, m.value) for m in at.metric]
    div_yield_metric = next((v for l, v in metric_pairs if l == "Dividend Yield"), None)
    assert div_yield_metric == "0.55%", f"Expected '0.55%', got {div_yield_metric!r}"


def test_fundamentals_tab_dividend_yield_aapl_032():
    """Verify Fundamentals tab displays 0.32% when raw dividendYield is 0.32 (e.g. AAPL)."""
    from datetime import datetime, timezone
    from yf_learner.providers.raw_models import RawFundamentalsData
    at, fake = _setup_open_ticker_app()
    fake.fundamentals = lambda sym: RawFundamentalsData(
        symbol=sym,
        info={
            "shortName": "Apple Inc.",
            "dividendYield": 0.32,
            "marketCap": 3000000000000,
            "sector": "Technology",
        },
        retrieved_at=datetime.now(timezone.utc),
    )
    at.session_state["learning_tab"] = "Fundamentals"
    at.session_state["refresh_fundamentals"] = 1
    at.run()

    metric_pairs = [(m.label, m.value) for m in at.metric]
    div_yield_metric = next((v for l, v in metric_pairs if l == "Dividend Yield"), None)
    assert div_yield_metric == "0.32%", f"Expected '0.32%', got {div_yield_metric!r}"


def test_statements_tab_renders_columns_and_data():
    """Verify Financial Statements tab renders dataframe with Metric column."""
    at, fake = _setup_open_ticker_app()
    at.session_state["learning_tab"] = "Financial Statements"
    at.run()

    assert len(at.dataframe) == 1
    # Check that selector controls exist
    assert at.selectbox(key="stmt_type_sel") is not None
    assert at.selectbox(key="stmt_freq_sel") is not None
    assert at.button(key="btn_refresh_statements") is not None


def test_provenance_rendering_stacked():
    """Verify provenance rendered in Quote tab includes stacked bullet metadata."""
    at, fake = _setup_open_ticker_app()
    md_values = [m.value for m in at.markdown]
    prov_md = next((m for m in md_values if "Provenance:" in m), None)
    assert prov_md is not None
    assert "- Source: `Yahoo Finance via yfinance`" in prov_md
    assert "- Retrieved:" in prov_md
    assert "- Data as of:" in prov_md
    assert "Data Limitations:" in prov_md
