"""Tests for finance-term tooltip lookup and column metadata."""

from __future__ import annotations

from contextlib import nullcontext

import streamlit as st

from yf_learner.ui.glossary import GLOSSARY, get_glossary_entry, get_help
from yf_learner.ui.layout import (
    build_analyst_table_column_config,
    build_history_column_config,
    build_statement_column_config,
    render_metric_grid,
    render_profile_grid,
)


REQUIRED_LABELS = (
    "Last Price",
    "Previous Close",
    "Open",
    "Day High / Low",
    "52-Week Range",
    "Volume",
    "Average Volume",
    "Market Cap",
    "Currency",
    "Exchange",
    "Timezone",
    "Latest Close",
    "High",
    "Low",
    "Close",
    "Period",
    "Interval",
    "Auto-adjust prices",
    "Corporate Actions",
    "Dividends",
    "Stock Splits",
    "Quote Type",
    "Sector",
    "Industry",
    "Employees",
    "Enterprise Value",
    "Trailing P/E",
    "Forward P/E",
    "Price / Book",
    "Dividend Yield",
    "Beta",
    "Income Statement",
    "Balance Sheet",
    "Cash Flow",
    "Annual",
    "Quarterly",
    "Financial Metric",
    "Recommendations",
    "Price Targets",
    "Current Target",
    "Low Target",
    "Mean Target",
    "Median Target",
    "High Target",
    "Earnings Estimates",
    "Revenue Estimates",
    "Growth Estimates",
    "Buy",
    "Hold",
    "Sell",
    "Strong Buy",
    "Press Releases",
    "Statement",
    "Frequency",
    "Dataset",
    "Feed",
    "Articles Count",
)


def test_required_finance_labels_have_nonempty_static_help():
    for label in REQUIRED_LABELS:
        help_text = get_help(label)
        assert help_text, f"Missing help text for {label!r}"
        assert "cookie" not in help_text.casefold()
        assert "crumb" not in help_text.casefold()
        assert "response body" not in help_text.casefold()


def test_representative_examples_are_beginner_friendly():
    for label in ("Last Price", "Market Cap", "Dividend Yield", "Price Targets"):
        entry = get_glossary_entry(label)
        assert entry is not None
        assert entry.example
        assert "Example:" in entry.as_help()


def test_lookup_is_case_insensitive_and_supports_yfinance_aliases():
    assert get_glossary_entry("last price") == get_glossary_entry("LAST PRICE")
    assert get_glossary_entry("Avg Volume (3M)").label == "Average Volume"
    assert get_glossary_entry("avg volume (10d)").label == "Average Volume"
    assert get_glossary_entry("trailing pe").label == "Trailing P/E"
    assert get_glossary_entry("PriceToBook").label == "Price / Book"
    assert get_glossary_entry("strongBuy").label == "Strong Buy"
    assert get_glossary_entry("Corporate Releases").label == "Press Releases"


def test_unknown_dynamic_labels_are_not_given_invented_definitions():
    assert get_glossary_entry("YahooInventedMetric") is None
    assert get_help(None) is None
    assert get_help(123) is None


def test_glossary_entries_are_static_and_compact():
    assert GLOSSARY
    assert all(entry.label and entry.explanation for entry in GLOSSARY.values())
    assert all(len(entry.as_help()) < 600 for entry in GLOSSARY.values())


def test_dataframe_column_configs_include_finance_help_metadata():
    history = build_history_column_config(actions=True)
    for label in ("Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"):
        assert history[label]["help"]

    statements = build_statement_column_config(["2025-09-30"])
    assert statements["Metric"]["help"] == get_help("Financial Metric")
    assert statements["2025-09-30"]["help"] == get_help("Reporting Period")

    analyst = build_analyst_table_column_config(["Buy", "Hold", "Unknown Yahoo Field"])
    assert analyst["Item"]["help"] == get_help("Analyst Field")
    assert analyst["Buy"]["help"] == get_help("Buy")
    assert analyst["Hold"]["help"] == get_help("Hold")
    assert analyst["Unknown Yahoo Field"]["help"] == get_help("Analyst Field")


def test_metric_and_profile_helpers_pass_glossary_help(monkeypatch):
    monkeypatch.setattr(st, "container", lambda **_: nullcontext())
    monkeypatch.setattr(st, "columns", lambda count: [nullcontext() for _ in range(count)])

    metric_calls: list[dict[str, object]] = []
    profile_calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(st, "metric", lambda **kwargs: metric_calls.append(kwargs))
    monkeypatch.setattr(st, "markdown", lambda body, **kwargs: profile_calls.append((body, kwargs)))

    render_metric_grid([("Last Price", "$190"), ("Avg Volume (3M)", "1M")], max_columns=2)
    render_profile_grid([("Sector", "Technology"), ("Industry", "Software")], columns=2)

    assert metric_calls[0]["help"] == get_help("Last Price")
    assert metric_calls[1]["help"] == get_help("Average Volume")
    assert profile_calls[0][1]["help"] == get_help("Sector")
    assert profile_calls[1][1]["help"] == get_help("Industry")
