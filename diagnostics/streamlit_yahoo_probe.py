"""Temporary standalone Yahoo Cloud diagnostic probe for evaluating upstream connectivity.

This module is a temporary diagnostic utility for cloud deployment readiness evaluation.
It does not expose financial payloads, cookies, crumbs, response headers, query strings,
or raw exception strings, and is kept strictly isolated from the production application.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
_src_path = str(_SRC_DIR)
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

import pandas as pd
import streamlit as st
import yfinance as yf

from yf_learner.providers.errors import ProviderFailureKind, ProviderUpstreamError

# Configure yfinance per diagnostic recovery gate specifications
yf.config.network.retries = 2
yf.config.debug.hide_exceptions = False
yf.config.debug.logging = False
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("curl_cffi").setLevel(logging.CRITICAL)

ALLOWED_SYMBOLS: tuple[str, ...] = ("AAPL", "MSFT")

ALLOWED_OPERATIONS: tuple[str, ...] = (
    "get_recommendations",
    "get_info",
    "get_analyst_price_targets",
    "get_earnings_estimate",
    "get_revenue_estimate",
    "get_growth_estimates",
)

FAILURE_CATEGORIES: tuple[str, ...] = (
    "rate_limited",
    "access_denied",
    "unavailable",
    "bad_response",
    "unknown",
)

CATEGORY_BASIS_DISPLAY_LABELS: dict[str, str] = {
    "insufficient_structured_evidence": "no structured HTTP status",
    "structured_http_status": "structured HTTP status",
}

_UNSET = object()


def get_curl_cffi_info(
    import_hook: Callable[[], Any] | None = None,
) -> tuple[bool | None, str | None]:
    """Check availability of `from curl_cffi import requests` import boundary and package version.

    Returns:
        (True, version) on successful import.
        (False, version or None) on ImportError.
        (None, version or None) on other exceptions (tri-state import failure).
    Never exposes exception details or inspects private modules.
    """
    version: str | None = None
    try:
        from importlib import metadata as importlib_metadata

        version = importlib_metadata.version("curl_cffi")
    except Exception:
        pass

    try:
        if import_hook is not None:
            requests = import_hook()
        else:
            from curl_cffi import requests  # type: ignore[import-not-found]

        if version is None:
            version = getattr(requests, "__version__", None)
            if version is None:
                try:
                    import curl_cffi  # type: ignore[import-not-found]

                    version = getattr(curl_cffi, "__version__", None)
                except Exception:
                    pass
        return True, str(version) if version is not None else None
    except ImportError:
        return False, str(version) if version is not None else None
    except Exception:
        return None, str(version) if version is not None else None


def is_yf_disable_curl_cffi_enabled() -> bool:
    """Check whether YF_DISABLE_CURL_CFFI is enabled per yfinance 1.7.0 behavior.

    In yfinance 1.7.0 (yfinance/_http.py):
    YF_DISABLE_CURL_CFFI is recognized only when val.lower() is exactly "1", "true", or "yes".
    Whitespace is not stripped, and "on" is not enabled.
    """
    raw = os.environ.get("YF_DISABLE_CURL_CFFI")
    if raw is None:
        return False
    return raw.lower() in ("1", "true", "yes")


def infer_http_backend(
    curl_cffi_importable: bool | None | object = _UNSET,
    yf_disable_enabled: bool | None | object = _UNSET,
) -> str:
    """Infer the HTTP backend used by yfinance without importing or inspecting private modules.

    Derivation rules:
    - If curl_cffi.requests is importable (True) and YF_DISABLE_CURL_CFFI is disabled (False):
      returns 'curl_cffi'.
    - If YF_DISABLE_CURL_CFFI is enabled (True) or curl_cffi.requests import failed with ImportError (False):
      returns 'requests_fallback'.
    - Otherwise (e.g. curl_cffi importability is unknown / None and toggle is disabled):
      returns 'unknown'.
    """
    if curl_cffi_importable is _UNSET:
        importable, _ = get_curl_cffi_info()
    else:
        importable = curl_cffi_importable

    if yf_disable_enabled is _UNSET:
        disabled = is_yf_disable_curl_cffi_enabled()
    else:
        disabled = bool(yf_disable_enabled)

    if disabled:
        return "requests_fallback"
    if importable is True:
        return "curl_cffi"
    if importable is False:
        return "requests_fallback"
    return "unknown"


def extract_structured_http_status(
    exc: BaseException, max_depth: int = 5
) -> tuple[int | None, str | None]:
    """Safely extract authoritative HTTP status code and its source attribute.

    Only public attributes (status_code, code) on the exception itself, its .response
    attribute, or within a bounded __cause__/__context__ chain are inspected.
    Returns (status_code, source_description) or (None, None).
    """
    queue: list[tuple[BaseException, str, int]] = [(exc, "exception", 0)]
    visited: set[int] = set()

    while queue:
        current, label, depth = queue.pop(0)
        current_id = id(current)
        if current_id in visited or depth > max_depth:
            continue
        visited.add(current_id)

        # 1. Direct status_code attribute on exception
        val = getattr(current, "status_code", None)
        if isinstance(val, int) and not isinstance(val, bool) and 100 <= val <= 599:
            return val, f"{label}.status_code"

        # 2. Direct code attribute on exception (e.g. urllib.error.HTTPError)
        val = getattr(current, "code", None)
        if isinstance(val, int) and not isinstance(val, bool) and 100 <= val <= 599:
            return val, f"{label}.code"

        # 3. Public response attribute on exception (e.g. requests / curl_cffi HTTPError)
        resp = getattr(current, "response", None)
        if resp is not None:
            resp_status = getattr(resp, "status_code", None)
            if (
                isinstance(resp_status, int)
                and not isinstance(resp_status, bool)
                and 100 <= resp_status <= 599
            ):
                return resp_status, f"{label}.response.status_code"
            resp_code = getattr(resp, "code", None)
            if (
                isinstance(resp_code, int)
                and not isinstance(resp_code, bool)
                and 100 <= resp_code <= 599
            ):
                return resp_code, f"{label}.response.code"

        # Traverse bounded cause and context
        cause = getattr(current, "__cause__", None)
        if isinstance(cause, BaseException) and id(cause) not in visited:
            queue.append((cause, f"{label}.__cause__", depth + 1))

        context = getattr(current, "__context__", None)
        if isinstance(context, BaseException) and id(context) not in visited:
            queue.append((context, f"{label}.__context__", depth + 1))

    return None, None


def extract_text_status_hint(exc: BaseException) -> int | None:
    """Extract a non-authoritative HTTP status hint matching ONLY the narrow 'HTTP Error NNN' form.

    Returns the integer code if matched, otherwise None.
    Incidental numeric text, generic crumb/blocked keywords, or arbitrary codes
    must NEVER be matched.
    """
    msg = str(exc)
    match = re.search(r"\bHTTP\s+Error\s+(\d{3})\b", msg, re.IGNORECASE)
    if match:
        try:
            code = int(match.group(1))
            if 100 <= code <= 599:
                return code
        except ValueError:
            pass
    return None


def classify_failure_category(
    exc: BaseException | None = None,
    structured_status: int | None = None,
) -> tuple[str, str]:
    """Classify failure strictly evidence-based from structured HTTP status.

    Only structured status values found by the bounded public status_code/code extractor
    can create HTTP categories:
    - 401, 403 -> access_denied
    - 429 -> rate_limited
    - 5xx (500-599) -> unavailable
    - 400, 404 -> bad_response
    - other structured codes -> unknown with basis 'structured_http_status'
    - no structured status -> unknown with basis 'insufficient_structured_evidence'

    Keyword, text, and exception-class based categorizations are completely removed.
    Returns (failure_category, failure_category_basis).
    """
    status = structured_status
    if status is None and exc is not None:
        status, _ = extract_structured_http_status(exc)

    if status is None:
        return "unknown", "insufficient_structured_evidence"

    basis = "structured_http_status"
    if status in (401, 403):
        return "access_denied", basis
    if status == 429:
        return "rate_limited", basis
    if 500 <= status <= 599:
        return "unavailable", basis
    if status in (400, 404):
        return "bad_response", basis
    return "unknown", basis


def describe_result_dimensions(result: Any) -> str:
    """Return a sanitized description of result dimensions or key count without exposing payload data."""
    if result is None:
        return "None (0 items)"

    if hasattr(result, "shape"):
        shape = getattr(result, "shape")
        if isinstance(shape, tuple):
            if len(shape) == 2:
                return f"{shape[0]} rows x {shape[1]} columns"
            if len(shape) == 1:
                return f"{shape[0]} items"
        return f"shape: {shape}"

    if isinstance(result, dict):
        return f"{len(result)} keys"

    if isinstance(result, (list, tuple, set)):
        return f"{len(result)} items"

    if isinstance(result, (str, bytes)):
        return f"1 item ({type(result).__name__})"

    if hasattr(result, "__len__"):
        try:
            return f"{len(result)} items"
        except TypeError:
            pass

    return f"1 item ({type(result).__name__})"


def execute_probe(
    symbol: str,
    operation: str,
    ticker_factory: Callable[[str], Any] = yf.Ticker,
) -> dict[str, Any]:
    """Execute exactly one yfinance operation against one fresh Ticker and return safe metadata."""
    if symbol not in ALLOWED_SYMBOLS:
        raise ValueError(f"Symbol '{symbol}' is not allowed. Must be one of {ALLOWED_SYMBOLS}.")
    if operation not in ALLOWED_OPERATIONS:
        raise ValueError(f"Operation '{operation}' is not allowed. Must be one of {ALLOWED_OPERATIONS}.")

    curl_cffi_importable, curl_cffi_version = get_curl_cffi_info()
    yf_disable_enabled = is_yf_disable_curl_cffi_enabled()
    inferred_backend = infer_http_backend(
        curl_cffi_importable=curl_cffi_importable,
        yf_disable_enabled=yf_disable_enabled,
    )

    metadata: dict[str, Any] = {
        "attempt_time_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "streamlit_version": getattr(st, "__version__", "unknown"),
        "yfinance_version": getattr(yf, "__version__", "unknown"),
        "curl_cffi_requests_importable": curl_cffi_importable,
        "curl_cffi_version": curl_cffi_version,
        "yf_disable_curl_cffi_enabled": yf_disable_enabled,
        "http_backend_inferred": inferred_backend,
        "symbol": symbol,
        "operation": operation,
        "success": False,
        "result_dimensions": "0 items",
        "exception_class": None,
        "structured_http_status": None,
        "http_status_source": None,
        "text_status_hint": None,
        "failure_category": None,
        "failure_category_basis": None,
    }

    try:
        ticker = ticker_factory(symbol)
        op_method = getattr(ticker, operation, None)
        if not callable(op_method):
            raise AttributeError(f"Ticker has no callable operation '{operation}'")
        raw_result = op_method()
        metadata["success"] = True
        metadata["result_dimensions"] = describe_result_dimensions(raw_result)
    except Exception as exc:
        metadata["success"] = False
        metadata["exception_class"] = type(exc).__name__
        structured_status, status_source = extract_structured_http_status(exc)
        text_status_hint = extract_text_status_hint(exc)
        failure_category, failure_category_basis = classify_failure_category(
            exc,
            structured_status=structured_status,
        )

        metadata["structured_http_status"] = structured_status
        metadata["http_status_source"] = status_source
        metadata["text_status_hint"] = text_status_hint
        metadata["failure_category"] = failure_category
        metadata["failure_category_basis"] = failure_category_basis
        metadata["result_dimensions"] = "0 items (error)"

    return metadata


def render_probe_ui() -> None:
    """Render the temporary standalone Streamlit diagnostic probe UI."""
    import streamlit as st
    st.set_page_config(
        page_title="Temporary Yahoo Cloud Diagnostic Probe",
        page_icon="🔍",
        layout="centered",
    )

    st.title("Temporary Yahoo Cloud Diagnostic Probe")
    st.warning(
        "⚠️ **TEMPORARY STANDALONE DIAGNOSTIC ONLY**\n\n"
        "This probe is an isolated, temporary diagnostic utility designed strictly to evaluate "
        "Yahoo Finance upstream connectivity in cloud environments. It makes **zero** requests "
        "on initial render. Exactly one click of the button performs exactly one selected getter "
        "on one fresh Ticker with no fallback getters or extra retries. It does not access, store, "
        "or display financial payloads, cookies, crumbs, response headers, query strings, or raw exception strings."
    )

    st.subheader("Probe Parameters")
    col1, col2 = st.columns(2)
    with col1:
        symbol = st.selectbox(
            "Symbol (allow-list: AAPL, MSFT)",
            options=list(ALLOWED_SYMBOLS),
            index=0,
            help="Sanctioned symbol for probe.",
        )
    with col2:
        operation = st.selectbox(
            "Operation (fundamentals & analyst getters)",
            options=list(ALLOWED_OPERATIONS),
            index=0,
            help="Sanctioned getter for probe.",
        )

    st.caption("Read-only mode: Zero network requests have been sent. One click makes exactly one live Yahoo request.")
    run_clicked = st.button("Run Diagnostic Probe", type="primary")

    if run_clicked:
        with st.spinner(f"Executing {operation} on fresh Ticker('{symbol}')..."):
            metadata = execute_probe(symbol, operation)

        if metadata["success"]:
            st.success(f"Probe succeeded: `{operation}` for `{symbol}`")
        else:
            basis_raw = metadata["failure_category_basis"]
            basis_display = (
                CATEGORY_BASIS_DISPLAY_LABELS.get(basis_raw, str(basis_raw))
                if basis_raw is not None
                else "None"
            )
            st.error(
                f"Probe failed: `{operation}` for `{symbol}` "
                f"(Failure Category: `{metadata['failure_category']}`, "
                f"Category Basis: `{basis_display}`, "
                f"Structured Status: `{metadata['structured_http_status']}`, "
                f"Text Hint: `{metadata['text_status_hint']}`)"
            )

        st.subheader("Sanitized Diagnostic Metadata")
        table_rows = [
            {"Field": "UTC Attempt Time", "Value": metadata["attempt_time_utc"]},
            {"Field": "Python Version", "Value": metadata["python_version"]},
            {"Field": "Streamlit Version", "Value": metadata["streamlit_version"]},
            {"Field": "yfinance Version", "Value": metadata["yfinance_version"]},
            {
                "Field": "curl_cffi.requests Importable",
                "Value": "Yes"
                if metadata["curl_cffi_requests_importable"] is True
                else ("No" if metadata["curl_cffi_requests_importable"] is False else "Unknown"),
            },
            {
                "Field": "curl_cffi Version",
                "Value": metadata["curl_cffi_version"] or "N/A",
            },
            {
                "Field": "YF_DISABLE_CURL_CFFI Enabled",
                "Value": "Yes" if metadata["yf_disable_curl_cffi_enabled"] else "No",
            },
            {"Field": "HTTP Backend (inferred)", "Value": metadata["http_backend_inferred"]},
            {"Field": "Symbol", "Value": metadata["symbol"]},
            {"Field": "Operation", "Value": metadata["operation"]},
            {"Field": "Outcome", "Value": "Success" if metadata["success"] else "Failure"},
            {
                "Field": "Result Shape / Key Count Only",
                "Value": metadata["result_dimensions"],
            },
            {
                "Field": "Exception Class",
                "Value": metadata["exception_class"] or "None",
            },
            {
                "Field": "Structured HTTP Status",
                "Value": str(metadata["structured_http_status"])
                if metadata["structured_http_status"] is not None
                else "None",
            },
            {
                "Field": "HTTP Status Source",
                "Value": metadata["http_status_source"] or "None",
            },
            {
                "Field": "Text Status Hint (non-authoritative)",
                "Value": str(metadata["text_status_hint"])
                if metadata["text_status_hint"] is not None
                else "None",
            },
            {
                "Field": "Failure Category",
                "Value": metadata["failure_category"] or "None",
            },
            {
                "Field": "Category Basis",
                "Value": (
                    CATEGORY_BASIS_DISPLAY_LABELS.get(
                        metadata["failure_category_basis"],
                        str(metadata["failure_category_basis"]),
                    )
                    if metadata["failure_category_basis"] is not None
                    else "None"
                ),
            },
        ]
        st.table(pd.DataFrame(table_rows))
        st.json(metadata)


if __name__ == "__main__":
    render_probe_ui()
