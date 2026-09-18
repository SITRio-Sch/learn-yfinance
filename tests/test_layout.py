"""Unit and AppTest tests for layout presentation helpers, column configs, and formatting."""

from __future__ import annotations

import math
from pathlib import Path
from streamlit.testing.v1 import AppTest

from yf_learner.ui.components import NOT_AVAILABLE, format_percent
from yf_learner.ui.layout import (
    build_analyst_table_column_config,
    build_history_column_config,
    build_statement_column_config,
    render_controls_row,
    render_dataframe,
    render_metric_grid,
    render_profile_grid,
)


def test_format_percent_canonical_ratio():
    """Verify format_percent multiplies canonical fractional ratio by 100 once."""
    # 0.0032 ratio -> 0.32%
    assert format_percent(0.0032) == "0.32%"
    # 0.025 ratio -> 2.50%
    assert format_percent(0.025) == "2.50%"
    # 0.0055 ratio -> 0.55%
    assert format_percent(0.0055) == "0.55%"
    # 0.0 ratio -> 0.00%
    assert format_percent(0.0) == "0.00%"


def test_format_percent_missing_and_malformed():
    """Verify format_percent returns NOT_AVAILABLE for missing, NaN, or non-numeric."""
    assert format_percent(None) == NOT_AVAILABLE
    assert format_percent(float("nan")) == NOT_AVAILABLE
    assert format_percent(float("inf")) == NOT_AVAILABLE
    assert format_percent("nan") == NOT_AVAILABLE
    assert format_percent("NaN") == NOT_AVAILABLE
    assert format_percent("None") == NOT_AVAILABLE
    assert format_percent("invalid") == NOT_AVAILABLE
    assert format_percent("") == NOT_AVAILABLE


def test_build_statement_column_config():
    """Verify statement column config provides wide metric column and medium periods."""
    periods = ["2025-09-30", "2024-09-30"]
    config = build_statement_column_config(periods, metric_column_name="Metric")
    assert "Metric" in config
    assert config["Metric"]["width"] == "large"
    assert config["2025-09-30"]["width"] == "medium"
    assert config["2024-09-30"]["width"] == "medium"


def test_build_history_column_config():
    """Verify history column config sets expected widths with and without actions."""
    cfg_base = build_history_column_config(actions=False)
    assert cfg_base["Date"]["width"] == "medium"
    assert cfg_base["Open"]["width"] == "small"
    assert cfg_base["High"]["width"] == "small"
    assert cfg_base["Low"]["width"] == "small"
    assert cfg_base["Close"]["width"] == "small"
    assert cfg_base["Volume"]["width"] == "medium"
    assert "Dividends" not in cfg_base

    cfg_actions = build_history_column_config(actions=True)
    assert "Dividends" in cfg_actions
    assert cfg_actions["Dividends"]["width"] == "small"
    assert "Stock Splits" in cfg_actions
    assert cfg_actions["Stock Splits"]["width"] == "small"


def test_build_analyst_table_column_config():
    """Verify analyst table column config sets Item to large and others to medium."""
    data_cols = ["Up", "Down", "Hold"]
    config = build_analyst_table_column_config(data_cols, item_column_name="Item")
    assert config["Item"]["width"] == "large"
    assert config["Up"]["width"] == "medium"
    assert config["Down"]["width"] == "medium"
    assert config["Hold"]["width"] == "medium"


def test_layout_helpers_in_apptest():
    """Verify layout containers and helpers execute cleanly within Streamlit AppTest."""

    def layout_runner():
        import streamlit as st
        from yf_learner.ui.layout import (
            build_statement_column_config,
            render_controls_row,
            render_dataframe,
            render_metric_grid,
            render_profile_grid,
        )

        with render_controls_row():
            st.selectbox("Test Period", ["1mo", "1y"], key="test_p")
            st.button("Test Refresh", key="test_btn")

        metrics = [
            ("M1", "Val 1"),
            ("M2", "Val 2"),
            ("M3", "Val 3"),
            ("M4", "Val 4"),
            ("M5", "Val 5"),
        ]
        render_metric_grid(metrics, max_columns=4)

        profiles = [
            ("Sector", "Tech"),
            ("Industry", "Software"),
            ("Country", "US"),
        ]
        render_profile_grid(profiles, columns=3)

        rows = [{"Metric": "NetIncomeFromContinuingOperations", "2025": "100M"}]
        cfg = build_statement_column_config(["2025"])
        render_dataframe(rows, column_config=cfg)

    at = AppTest.from_function(layout_runner).run()
    assert not at.exception
    assert at.selectbox(key="test_p").value == "1mo"
    assert at.button(key="test_btn") is not None
    assert len(at.metric) == 5
    assert len(at.dataframe) == 1


def test_styles_css_nested_metric_selectors_and_no_ellipsis():
    """Verify styles.css overrides nested stMarkdownContainer metric selector to prevent ellipsis."""
    css_path = Path(__file__).parent.parent / "src" / "yf_learner" / "ui" / "styles.css"
    assert css_path.is_file(), f"styles.css not found at {css_path}"
    css = css_path.read_text(encoding="utf-8")

    # Assert nested stMarkdownContainer selector with child combinator
    expected_nested_selector = 'div[data-testid="stMetricValue"] > div[data-testid="stMarkdownContainer"]'
    assert expected_nested_selector in css, f"Selector '{expected_nested_selector}' missing in styles.css"

    # Assert required properties are present
    assert "overflow: visible" in css
    assert "white-space: normal" in css
    assert "text-overflow: clip" in css
    assert "overflow-wrap: anywhere" in css

    # Assert parent stMetricValue and nested p element rules are also present
    assert 'div[data-testid="stMetricValue"]' in css
    assert 'div[data-testid="stMetricValue"] > div[data-testid="stMarkdownContainer"] > p' in css


def test_styles_css_keeps_native_help_tooltips_inside_narrow_viewports():
    """Verify native Streamlit help tooltips are constrained and can wrap."""
    css_path = Path(__file__).parent.parent / "src" / "yf_learner" / "ui" / "styles.css"
    css = css_path.read_text(encoding="utf-8")

    assert '[role="tooltip"]' in css
    assert "max-width: calc(100vw - 2rem) !important" in css
    assert '[data-testid="stTooltipContent"]' in css
    assert "overflow-wrap: anywhere !important" in css
    assert "word-break: break-word !important" in css


def _parse_css_rule_blocks(css_text: str) -> dict[str, dict[str, str]]:
    """Parse CSS text into normalized selector to declarations mapping."""
    import re
    clean_css = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    rules: dict[str, dict[str, str]] = {}
    for match in re.finditer(r"([^{}]+)\{([^}]+)\}", clean_css):
        raw_sel, raw_body = match.group(1), match.group(2)
        norm_sel = re.sub(r"\s*>\s*", " > ", " ".join(raw_sel.split())).strip()
        declarations: dict[str, str] = {}
        for decl in raw_body.split(";"):
            decl = decl.strip()
            if not decl or ":" not in decl:
                continue
            prop, val = decl.split(":", 1)
            declarations[prop.strip().lower()] = " ".join(val.split()).strip().lower()
        rules[norm_sel] = declarations
    return rules


def _assert_metric_anti_ellipsis_selectors(css_text: str) -> None:
    """Assert all three exact metric anti-ellipsis selectors and their required properties exist."""
    rules = _parse_css_rule_blocks(css_text)

    parent_sel = 'div[data-testid="stMetricValue"]'
    container_sel = 'div[data-testid="stMetricValue"] > div[data-testid="stMarkdownContainer"]'
    p_sel = 'div[data-testid="stMetricValue"] > div[data-testid="stMarkdownContainer"] > p'

    if parent_sel not in rules:
        raise AssertionError(f"Parent selector '{parent_sel}' missing")
    if container_sel not in rules:
        raise AssertionError(f"Container selector '{container_sel}' missing")
    if p_sel not in rules:
        raise AssertionError(f"Paragraph selector '{p_sel}' missing")

    # Parent properties
    parent_props = rules[parent_sel]
    assert parent_props.get("min-width") == "0 !important", f"parent min-width: {parent_props.get('min-width')}"
    assert parent_props.get("max-width") == "100% !important", f"parent max-width: {parent_props.get('max-width')}"
    assert parent_props.get("overflow") == "visible !important", f"parent overflow: {parent_props.get('overflow')}"
    assert parent_props.get("white-space") == "normal !important", f"parent white-space: {parent_props.get('white-space')}"
    assert parent_props.get("text-overflow") == "clip !important", f"parent text-overflow: {parent_props.get('text-overflow')}"

    # Container properties
    container_props = rules[container_sel]
    assert container_props.get("display") == "block !important", f"container display: {container_props.get('display')}"
    assert container_props.get("width") == "100% !important", f"container width: {container_props.get('width')}"
    assert container_props.get("min-width") == "0 !important", f"container min-width: {container_props.get('min-width')}"
    assert container_props.get("max-width") == "100% !important", f"container max-width: {container_props.get('max-width')}"
    assert container_props.get("overflow") == "visible !important", f"container overflow: {container_props.get('overflow')}"
    assert container_props.get("white-space") == "normal !important", f"container white-space: {container_props.get('white-space')}"
    assert container_props.get("text-overflow") == "clip !important", f"container text-overflow: {container_props.get('text-overflow')}"
    assert container_props.get("overflow-wrap") == "anywhere !important", f"container overflow-wrap: {container_props.get('overflow-wrap')}"
    assert container_props.get("word-break") == "normal !important", f"container word-break: {container_props.get('word-break')}"

    # Paragraph properties
    p_props = rules[p_sel]
    assert p_props.get("display") == "block !important", f"p display: {p_props.get('display')}"
    assert p_props.get("width") == "100% !important", f"p width: {p_props.get('width')}"
    assert p_props.get("min-width") == "0 !important", f"p min-width: {p_props.get('min-width')}"
    assert p_props.get("max-width") == "100% !important", f"p max-width: {p_props.get('max-width')}"
    assert p_props.get("margin") == "0 !important", f"p margin: {p_props.get('margin')}"
    assert p_props.get("padding") == "0 !important", f"p padding: {p_props.get('padding')}"
    assert p_props.get("overflow") == "visible !important", f"p overflow: {p_props.get('overflow')}"
    assert p_props.get("white-space") == "normal !important", f"p white-space: {p_props.get('white-space')}"
    assert p_props.get("text-overflow") == "clip !important", f"p text-overflow: {p_props.get('text-overflow')}"
    assert p_props.get("overflow-wrap") == "anywhere !important", f"p overflow-wrap: {p_props.get('overflow-wrap')}"
    assert p_props.get("word-break") == "normal !important", f"p word-break: {p_props.get('word-break')}"


def test_styles_css_metric_anti_ellipsis_exact_selectors_regression():
    """Robust regression test asserting the 3 exact selector blocks and all critical properties.

    Verifies that styles.css contains the parent, container, and paragraph selectors with
    display, overflow, white-space, text-overflow, widths, and wrapping, and fails if only the
    parent selector is present.
    """
    import pytest

    css_path = Path(__file__).parent.parent / "src" / "yf_learner" / "ui" / "styles.css"
    css = css_path.read_text(encoding="utf-8")

    # 1. Must succeed on actual stylesheet
    _assert_metric_anti_ellipsis_selectors(css)

    # 2. Must fail if only the parent selector is present
    only_parent_css = '''
    div[data-testid="stMetricValue"] {
        min-width: 0 !important;
        max-width: 100% !important;
        overflow: visible !important;
        white-space: normal !important;
        text-overflow: clip !important;
    }
    '''
    with pytest.raises(AssertionError, match="missing"):
        _assert_metric_anti_ellipsis_selectors(only_parent_css)
