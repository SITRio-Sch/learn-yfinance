"""UI AppTest tests for missing fields, empty states, error states, and refresh failure."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from tests.fakes import FakeMarketDataProvider
from yf_learner.services.market_data import MarketDataService
from yf_learner.services.request_gate import RequestGate
from yf_learner.ui.cache import set_service_override

APP_PATH = str((Path(__file__).parent.parent / "app.py").resolve())


def test_missing_values_render_as_not_available():
    fake = FakeMarketDataProvider()
    # Inject missing/None values into quote
    fake.sample_fast_info = {
        "last_price": 100.0,
        "previous_close": None,
        "open": None,
        "day_high": None,
        "day_low": None,
        "year_high": None,
        "year_low": None,
        "last_volume": None,
        "three_month_average_volume": None,
        "ten_day_average_volume": None,
        "currency": None,
        "exchange": None,
        "timezone": None,
        "market_cap": None,
    }
    fake.sample_metadata = {"regularMarketTime": None}
    service = MarketDataService(fake, gate=RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None))
    set_service_override(service)

    at = AppTest.from_file(APP_PATH, default_timeout=10).run()
    at.text_input(key="search_query_input").input("AAPL").run()
    at.button(key="FormSubmitter:search_form-Search").click().run()
    at.button(key="open_ticker_btn").click().run()

    # Verify 'Not available' is present in metrics instead of None / 0
    metric_values = [m.value for m in at.metric]
    assert "Not available" in metric_values
    assert "None" not in metric_values
    assert "nan" not in [str(v).lower() for v in metric_values]


def test_empty_news_state():
    fake = FakeMarketDataProvider()
    fake.sample_search_quotes = [{"symbol": "EMPTY", "shortname": "Empty News Corp"}]
    service = MarketDataService(fake, gate=RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None))
    set_service_override(service)

    at = AppTest.from_file(APP_PATH, default_timeout=10).run()
    at.text_input(key="search_query_input").input("EMPTY").run()
    at.button(key="FormSubmitter:search_form-Search").click().run()
    at.button(key="open_ticker_btn").click().run()

    # Override news items to empty
    fake.sample_fast_info["last_price"] = 10.0
    from datetime import datetime, timezone
    from yf_learner.providers.raw_models import RawNewsData

    fake.news = lambda symbol, feed, count: RawNewsData(symbol=symbol, feed=feed, raw_items=[], retrieved_at=datetime.now(timezone.utc))

    # Switch to news
    at.session_state["learning_tab"] = "News"
    at.run()
    assert any("No news articles are available" in info.value for info in at.info)


def test_rate_limit_and_timeout_error_states():
    fake = FakeMarketDataProvider()
    service = MarketDataService(fake, gate=RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None))
    set_service_override(service)

    at = AppTest.from_file(APP_PATH, default_timeout=10).run()
    at.text_input(key="search_query_input").input("AAPL").run()
    at.button(key="FormSubmitter:search_form-Search").click().run()
    at.button(key="open_ticker_btn").click().run()

    # Now make history raise Rate Limit
    fake.error_by_method["history"] = Exception("HTTP 429 Too Many Requests")
    at.session_state["learning_tab"] = "History"
    at.run()
    assert any("limiting requests right now" in err.value for err in at.error)

    # Now make fundamentals raise Timeout
    fake.error_by_method["fundamentals"] = TimeoutError("Timed out")
    at.session_state["learning_tab"] = "Fundamentals"
    at.run()
    assert any("did not respond in time" in err.value for err in at.error)


def test_refresh_failure_removes_old_data():
    fake = FakeMarketDataProvider()
    service = MarketDataService(fake, gate=RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None))
    set_service_override(service)

    at = AppTest.from_file(APP_PATH, default_timeout=10).run()
    at.text_input(key="search_query_input").input("AAPL").run()
    at.button(key="FormSubmitter:search_form-Search").click().run()
    at.button(key="open_ticker_btn").click().run()

    # Initial successful quote rendered
    assert len(at.metric) > 0
    assert len(at.error) == 0

    # Inject error for subsequent refresh
    fake.error_to_raise = Exception("HTTP 429 Rate limited")
    at.button(key="btn_refresh_quote").click().run()

    # Now error is displayed, and previous successful metric cards are not rendered
    assert any("limiting requests right now" in err.value for err in at.error)
    assert len(at.metric) == 0


def test_missing_fundamentals_values_render_as_not_available():
    """Verify missing, NaN, or None fundamentals values render as 'Not available'."""
    fake = FakeMarketDataProvider()
    service = MarketDataService(fake, gate=RequestGate(min_interval_seconds=0.0, sleep_func=lambda s: None))
    set_service_override(service)

    from datetime import datetime, timezone
    from yf_learner.providers.raw_models import RawFundamentalsData

    # Inject missing/NaN values while keeping basic name
    fake.fundamentals = lambda symbol: RawFundamentalsData(
        symbol=symbol,
        info={
            "shortName": "Partial Fundamentals Inc",
            "marketCap": 1000000,
            "trailingPE": float("nan"),
            "forwardPE": None,
            "dividendYield": None,
            "priceToBook": "nan",
        },
        retrieved_at=datetime.now(timezone.utc),
    )

    at = AppTest.from_file(APP_PATH, default_timeout=10).run()
    at.text_input(key="search_query_input").input("AAPL").run()
    at.button(key="FormSubmitter:search_form-Search").click().run()
    at.button(key="open_ticker_btn").click().run()

    at.session_state["learning_tab"] = "Fundamentals"
    at.run()

    metric_values = [m.value for m in at.metric]
    assert "Not available" in metric_values
    assert "nan" not in [str(v).lower() for v in metric_values]
    assert "none" not in [str(v).lower() for v in metric_values]
