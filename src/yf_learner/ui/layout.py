"""Presentation-only layout helpers for responsive controls, metrics, and dataframes."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

import streamlit as st

from yf_learner.ui.glossary import get_help


@contextmanager
def render_controls_row(
    gap: str = "small",
    vertical_alignment: str = "bottom",
    key: str | None = None,
) -> Iterator[None]:
    """Render a native horizontal wrapping container for interactive controls.

    Aligns elements (such as selectboxes, checkboxes, and buttons) cleanly,
    allowing them to wrap onto multiple rows when space is constrained.
    """
    with st.container(
        horizontal=True,
        wrap=True,
        gap=gap,
        vertical_alignment=vertical_alignment,
        key=key,
    ):
        yield


def render_metric_grid(
    metrics: Sequence[tuple[str, str] | tuple[str, str, str | None]],
    max_columns: int = 4,
    key_prefix: str | None = None,
) -> None:
    """Render a responsive group of st.metric items.

    Renders metrics in chunked rows using st.columns so that desktop layouts
    stay dense and clean while CSS media queries adapt to 2-column on tablets
    and 1-column on mobile.
    """
    if not metrics:
        return

    with st.container():
        for row_start in range(0, len(metrics), max_columns):
            chunk = metrics[row_start : row_start + max_columns]
            cols = st.columns(len(chunk))
            for idx, (col, item) in enumerate(zip(cols, chunk)):
                with col:
                    if len(item) == 3 and item[2] is not None:
                        st.metric(
                            label=item[0],
                            value=item[1],
                            delta=item[2],
                            help=get_help(item[0]),
                        )
                    else:
                        st.metric(
                            label=item[0],
                            value=item[1],
                            help=get_help(item[0]),
                        )


def render_profile_grid(
    items: Sequence[tuple[str, str]],
    columns: int = 3,
) -> None:
    """Render company profile items across adaptive columns."""
    if not items:
        return

    with st.container():
        for i in range(0, len(items), columns):
            chunk = items[i : i + columns]
            cols = st.columns(len(chunk))
            for col, (label, val) in zip(cols, chunk):
                with col:
                    st.markdown(f"**{label}:** {val}", help=get_help(label))


def build_history_column_config(actions: bool = False) -> dict[str, Any]:
    """Construct explicit column configuration for the historical prices table."""
    config: dict[str, Any] = {
        "Date": st.column_config.TextColumn("Date", width="medium"),
        "Open": st.column_config.TextColumn("Open", width="small", help=get_help("Open")),
        "High": st.column_config.TextColumn("High", width="small", help=get_help("High")),
        "Low": st.column_config.TextColumn("Low", width="small", help=get_help("Low")),
        "Close": st.column_config.TextColumn("Close", width="small", help=get_help("Close")),
        "Volume": st.column_config.TextColumn("Volume", width="medium", help=get_help("Volume")),
    }
    if actions:
        config["Dividends"] = st.column_config.TextColumn(
            "Dividends",
            width="small",
            help=get_help("Dividends"),
        )
        config["Stock Splits"] = st.column_config.TextColumn(
            "Stock Splits",
            width="small",
            help=get_help("Stock Splits"),
        )
    return config


def build_statement_column_config(
    period_columns: Sequence[str],
    metric_column_name: str = "Metric",
) -> dict[str, Any]:
    """Construct explicit column configuration for financial statement tables.

    Provides a wide Metric column to prevent truncation of long Yahoo accounting
    identifiers, while giving predictable medium widths to period columns.
    """
    config: dict[str, Any] = {
        metric_column_name: st.column_config.TextColumn(
            "Financial Metric",
            help=get_help("Financial Metric"),
            width="large",
        ),
    }
    for col_name in period_columns:
        config[col_name] = st.column_config.TextColumn(
            str(col_name),
            width="medium",
            help=get_help("Reporting Period") if str(col_name) else None,
        )
    return config


def build_analyst_table_column_config(
    data_columns: Sequence[str],
    item_column_name: str = "Item",
) -> dict[str, Any]:
    """Construct explicit column configuration for tabular analyst datasets."""
    config: dict[str, Any] = {
        item_column_name: st.column_config.TextColumn(
            "Item",
            width="large",
            help=get_help("Analyst Field"),
        ),
    }
    for col_name in data_columns:
        config[col_name] = st.column_config.TextColumn(
            str(col_name),
            width="medium",
            help=get_help(col_name) or get_help("Analyst Field"),
        )
    return config


def render_dataframe(
    data: Any,
    column_config: Mapping[str, Any] | None = None,
    hide_index: bool = True,
    width: str = "stretch",
) -> None:
    """Render a dataframe with explicit column configuration and responsive container."""
    st.dataframe(
        data,
        column_config=column_config,
        hide_index=hide_index,
        width=width,
    )
