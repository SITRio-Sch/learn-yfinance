"""Offline unit tests for standalone Yahoo Cloud diagnostic probe."""

from __future__ import annotations

import json
import os
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
import yfinance as yf

from diagnostics.streamlit_yahoo_probe import (
    ALLOWED_OPERATIONS,
    ALLOWED_SYMBOLS,
    CATEGORY_BASIS_DISPLAY_LABELS,
    FAILURE_CATEGORIES,
    classify_failure_category,
    describe_result_dimensions,
    execute_probe,
    extract_structured_http_status,
    extract_text_status_hint,
    get_curl_cffi_info,
    infer_http_backend,
    is_yf_disable_curl_cffi_enabled,
    render_probe_ui,
)
from yf_learner.providers.errors import ProviderFailureKind, ProviderUpstreamError

PROBE_FILE_PATH = str((Path(__file__).parent.parent / "diagnostics" / "streamlit_yahoo_probe.py").resolve())


def test_yfinance_config_initialization():
    """Verify probe initializes yfinance with required network and debug settings."""
    assert yf.config.network.retries == 2
    assert yf.config.debug.hide_exceptions is False
    assert yf.config.debug.logging is False


def test_allowed_symbols_and_operations():
    """Verify only sanctioned symbols and operations are exposed, defaulting to get_recommendations."""
    assert ALLOWED_SYMBOLS == ("AAPL", "MSFT")
    # AAPL get_recommendations must be index 0 so it defaults as the first/cold call
    assert ALLOWED_OPERATIONS[0] == "get_recommendations"
    assert set(ALLOWED_OPERATIONS) == {
        "get_recommendations",
        "get_info",
        "get_analyst_price_targets",
        "get_earnings_estimate",
        "get_revenue_estimate",
        "get_growth_estimates",
    }
    assert set(FAILURE_CATEGORIES) == {
        "rate_limited",
        "access_denied",
        "unavailable",
        "bad_response",
        "unknown",
    }


class TestEnvironmentToggleSemantics:
    """Exact environment semantics for YF_DISABLE_CURL_CFFI matching yfinance 1.7.0 _http.py."""

    @pytest.mark.parametrize(
        "val",
        ["1", "true", "True", "TRUE", "tRuE", "yes", "Yes", "YES", "yEs"],
    )
    def test_enabled_values(self, monkeypatch, val):
        monkeypatch.setenv("YF_DISABLE_CURL_CFFI", val)
        assert is_yf_disable_curl_cffi_enabled() is True

    @pytest.mark.parametrize(
        "val",
        [
            "on",
            "ON",
            "On",
            "0",
            "false",
            "False",
            "no",
            "No",
            "disabled",
            "off",
            "",
            " 1",
            "1 ",
            "  1  ",
            " true ",
            "yes ",
            " true",
        ],
    )
    def test_not_enabled_values(self, monkeypatch, val):
        monkeypatch.setenv("YF_DISABLE_CURL_CFFI", val)
        assert is_yf_disable_curl_cffi_enabled() is False

    def test_unset_value(self, monkeypatch):
        monkeypatch.delenv("YF_DISABLE_CURL_CFFI", raising=False)
        assert is_yf_disable_curl_cffi_enabled() is False


class TestImportBoundaryAndTriState:
    """Check import boundary behavior and tri-state failure handling."""

    def test_root_package_alone_insufficient(self):
        def failing_requests_import():
            raise ImportError("No module named 'curl_cffi.requests'")

        available, version = get_curl_cffi_info(import_hook=failing_requests_import)
        assert available is False
        # Version from safe package metadata should be preserved if available
        if version is not None:
            assert isinstance(version, str)

    def test_import_success_returns_true(self):
        mock_req = MagicMock()
        mock_req.__version__ = "0.16.3"
        available, version = get_curl_cffi_info(import_hook=lambda: mock_req)
        assert available is True
        assert version is not None

    def test_tri_state_import_failure(self):
        # 1. Success -> True
        avail_ok, _ = get_curl_cffi_info(import_hook=lambda: MagicMock())
        assert avail_ok is True

        # 2. ImportError -> False
        def raise_import_err():
            raise ImportError("No module named curl_cffi.requests")

        avail_importerr, _ = get_curl_cffi_info(import_hook=raise_import_err)
        assert avail_importerr is False

        # 3. Other exception (e.g. RuntimeError / OSError / DLL fail) -> None (unknown)
        def raise_runtime_err():
            raise RuntimeError("DLL initialization failed")

        avail_other, _ = get_curl_cffi_info(import_hook=raise_runtime_err)
        assert avail_other is None

        def raise_os_err():
            raise OSError("Library not found")

        avail_os, _ = get_curl_cffi_info(import_hook=raise_os_err)
        assert avail_os is None


class TestBackendInferenceTruthTable:
    """Verify backend inference truth table without inspecting private modules."""

    @pytest.mark.parametrize(
        ("importable", "toggle_enabled", "expected"),
        [
            (True, False, "curl_cffi"),
            (True, True, "requests_fallback"),
            (False, False, "requests_fallback"),
            (False, True, "requests_fallback"),
            (None, False, "unknown"),
            (None, True, "requests_fallback"),
        ],
    )
    def test_backend_inference_cases(self, importable, toggle_enabled, expected):
        inferred = infer_http_backend(
            curl_cffi_importable=importable,
            yf_disable_enabled=toggle_enabled,
        )
        assert inferred == expected


class TestExtractStructuredHttpStatus:
    def test_extract_from_status_code_attribute(self):
        exc = Exception("custom error")
        setattr(exc, "status_code", 429)
        status, source = extract_structured_http_status(exc)
        assert status == 429
        assert source == "exception.status_code"

    def test_extract_from_code_attribute(self):
        exc = urllib.error.HTTPError(
            url="https://finance.yahoo.com",
            code=403,
            msg="Forbidden",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )
        status, source = extract_structured_http_status(exc)
        assert status == 403
        assert source == "exception.code"

    def test_extract_from_nested_response_object(self):
        resp = MagicMock()
        resp.status_code = 502
        exc = Exception("gateway failure")
        setattr(exc, "response", resp)
        status, source = extract_structured_http_status(exc)
        assert status == 502
        assert source == "exception.response.status_code"

    def test_extract_from_bounded_cause_chain(self):
        inner = urllib.error.HTTPError(
            url="https://finance.yahoo.com",
            code=401,
            msg="Unauthorized",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )
        outer = RuntimeError("Failed request")
        outer.__cause__ = inner
        status, source = extract_structured_http_status(outer)
        assert status == 401
        assert source == "exception.__cause__.code"

    def test_extract_from_bounded_context_chain(self):
        resp = MagicMock()
        resp.status_code = 503
        inner = Exception("Service unavailable")
        inner.response = resp  # type: ignore[attr-defined]

        outer = RuntimeError("Wrapper exception")
        outer.__context__ = inner
        status, source = extract_structured_http_status(outer)
        assert status == 503
        assert source == "exception.__context__.response.status_code"

    def test_circular_cause_context_does_not_infinite_loop(self):
        exc1 = Exception("First")
        exc2 = Exception("Second")
        exc1.__cause__ = exc2
        exc2.__cause__ = exc1
        status, source = extract_structured_http_status(exc1)
        assert status is None
        assert source is None

    def test_depth_bounded_traversal(self):
        curr = Exception("base")
        for i in range(10):
            nxt = Exception(f"wrap_{i}")
            nxt.__cause__ = curr
            curr = nxt
        deep_target = urllib.error.HTTPError("url", 403, "msg", None, None)  # type: ignore[arg-type]
        curr.__cause__.__cause__.__cause__.__cause__.__cause__.__cause__ = deep_target  # depth 6

        status, source = extract_structured_http_status(curr, max_depth=5)
        assert status is None
        assert source is None


class TestStructuredHttpStatusCategories:
    """Strictly evidence-based failure categorization from structured status codes."""

    @pytest.mark.parametrize("code", [401, 403])
    def test_access_denied_from_structured_status(self, code):
        exc = Exception("error")
        setattr(exc, "status_code", code)
        cat, basis = classify_failure_category(exc)
        assert cat == "access_denied"
        assert basis == "structured_http_status"
        assert type(basis) is str

    def test_rate_limited_from_structured_status(self):
        exc = Exception("error")
        setattr(exc, "status_code", 429)
        cat, basis = classify_failure_category(exc)
        assert cat == "rate_limited"
        assert basis == "structured_http_status"
        assert type(basis) is str

    @pytest.mark.parametrize("code", [500, 502, 503, 504, 599])
    def test_unavailable_from_structured_status(self, code):
        exc = Exception("error")
        setattr(exc, "status_code", code)
        cat, basis = classify_failure_category(exc)
        assert cat == "unavailable"
        assert basis == "structured_http_status"
        assert type(basis) is str

    @pytest.mark.parametrize("code", [400, 404])
    def test_bad_response_from_structured_status(self, code):
        exc = Exception("error")
        setattr(exc, "status_code", code)
        cat, basis = classify_failure_category(exc)
        assert cat == "bad_response"
        assert basis == "structured_http_status"
        assert type(basis) is str

    @pytest.mark.parametrize("code", [418, 402, 200, 301, 302])
    def test_other_structured_status_unknown(self, code):
        exc = Exception("error")
        setattr(exc, "status_code", code)
        cat, basis = classify_failure_category(exc)
        assert cat == "unknown"
        assert basis == "structured_http_status"
        assert type(basis) is str

    def test_no_structured_status_unknown(self):
        exc = Exception("unstructured failure")
        cat, basis = classify_failure_category(exc)
        assert cat == "unknown"
        assert basis == "insufficient_structured_evidence"
        assert type(basis) is str


class TestTextStatusHintAndSeparation:
    """Text status hint remains non-authoritative metadata and never creates a category."""

    @pytest.mark.parametrize(
        ("msg", "expected_hint"),
        [
            ("HTTP Error 401: Unauthorized", 401),
            ("HTTP Error 403: Forbidden", 403),
            ("HTTP Error 429: Too Many Requests", 429),
            ("HTTP Error 503: Service Unavailable", 503),
            ("HTTP Error 404: Not Found", 404),
        ],
    )
    def test_text_only_http_status_hint_remains_unknown(self, msg, expected_hint):
        exc = Exception(msg)
        hint = extract_text_status_hint(exc)
        assert hint == expected_hint

        cat, basis = classify_failure_category(exc)
        assert cat == "unknown"
        assert basis == "insufficient_structured_evidence"
        assert type(basis) is str

    def test_incidental_numeric_text_does_not_extract_as_hint(self):
        incidental_cases = [
            Exception("processed 503 rows"),
            ValueError("account 401k"),
            ValueError("403"),
            ValueError("status code: 403"),
            KeyError("crumb"),
            Exception("unrelated thread blocked on resource"),
        ]
        for exc in incidental_cases:
            assert extract_text_status_hint(exc) is None
            cat, basis = classify_failure_category(exc)
            assert cat == "unknown"
            assert basis == "insufficient_structured_evidence"
            assert type(basis) is str

    def test_conflicting_structured_status_wins_over_text(self):
        exc = Exception("HTTP Error 404: Not Found")
        setattr(exc, "status_code", 429)

        structured, source = extract_structured_http_status(exc)
        hint = extract_text_status_hint(exc)
        cat, basis = classify_failure_category(exc, structured_status=structured)

        assert structured == 429
        assert source == "exception.status_code"
        assert hint == 404
        assert cat == "rate_limited"
        assert basis == "structured_http_status"
        assert type(basis) is str

    def test_conflicting_structured_503_wins_over_text_403(self):
        exc = Exception("HTTP Error 403: Forbidden")
        setattr(exc, "status_code", 503)

        structured, _ = extract_structured_http_status(exc)
        hint = extract_text_status_hint(exc)
        cat, basis = classify_failure_category(exc, structured_status=structured)

        assert structured == 503
        assert hint == 403
        assert cat == "unavailable"
        assert basis == "structured_http_status"
        assert type(basis) is str


class TestGenericExceptionsDoNotInventCategory:
    """Keywords, exception classes, and phrases must never invent a category without structured status."""

    @pytest.mark.parametrize(
        "exc",
        [
            ValueError("Invalid crumb"),
            KeyError("crumb"),
            Exception("Rate limit exceeded"),
            Exception("too many requests"),
            TimeoutError("timed out"),
            ConnectionError("connection refused"),
            OSError("network unreachable"),
            json.JSONDecodeError("expecting value", "doc", 0),
            Exception("unauthorized"),
            Exception("forbidden"),
            Exception("permission denied"),
            Exception("service unavailable"),
            ProviderUpstreamError(kind=ProviderFailureKind.RATE_LIMITED, operation="test", http_status=None),
            ProviderUpstreamError(kind=ProviderFailureKind.ACCESS_DENIED, operation="test", http_status=None),
            ProviderUpstreamError(kind=ProviderFailureKind.UNAVAILABLE, operation="test", http_status=None),
            ProviderUpstreamError(kind=ProviderFailureKind.BAD_RESPONSE, operation="test", http_status=None),
        ],
    )
    def test_generic_phrases_and_classes_map_to_unknown(self, exc):
        cat, basis = classify_failure_category(exc)
        assert cat == "unknown"
        assert basis == "insufficient_structured_evidence"
        assert type(basis) is str


class TestDescribeResultDimensions:
    def test_dataframe_dimensions(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        assert describe_result_dimensions(df) == "3 rows x 2 columns"

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        assert describe_result_dimensions(df) == "0 rows x 0 columns"

    def test_series_length(self):
        series = pd.Series([10, 20, 30])
        assert describe_result_dimensions(series) == "3 items"

    def test_dict_key_count(self):
        data = {"x": 100, "y": 200, "z": 300}
        assert describe_result_dimensions(data) == "3 keys"
        assert describe_result_dimensions({}) == "0 keys"

    def test_list_dimensions(self):
        assert describe_result_dimensions([1, 2, 3, 4]) == "4 items"
        assert describe_result_dimensions([]) == "0 items"

    def test_none_value(self):
        assert describe_result_dimensions(None) == "None (0 items)"


class TestExecuteProbe:
    def test_allow_list_validation(self):
        with pytest.raises(ValueError, match="Symbol 'GOOG' is not allowed"):
            execute_probe("GOOG", "get_recommendations")

        with pytest.raises(ValueError, match="Operation 'download' is not allowed"):
            execute_probe("AAPL", "download")

    def test_execute_probe_one_call_no_fallback(self):
        mock_ticker = MagicMock()
        mock_ticker.get_recommendations.return_value = pd.DataFrame({"col1": [1, 2]})
        mock_factory = MagicMock(return_value=mock_ticker)

        meta = execute_probe("AAPL", "get_recommendations", ticker_factory=mock_factory)

        mock_factory.assert_called_once_with("AAPL")
        mock_ticker.get_recommendations.assert_called_once_with()
        assert mock_ticker.method_calls == [("get_recommendations", (), {})]

        assert meta["symbol"] == "AAPL"
        assert meta["operation"] == "get_recommendations"
        assert meta["success"] is True
        assert meta["exception_class"] is None
        assert meta["structured_http_status"] is None
        assert meta["http_status_source"] is None
        assert meta["text_status_hint"] is None
        assert meta["failure_category"] is None
        assert meta["failure_category_basis"] is None
        assert "safe_reason" not in meta
        assert "http_status" not in meta
        assert meta["curl_cffi_requests_importable"] in (True, False, None)
        assert meta["yf_disable_curl_cffi_enabled"] is False
        assert meta["http_backend_inferred"] in ("curl_cffi", "requests_fallback", "unknown")
        assert "yf_disable_curl_cffi_set" not in meta
        assert meta["result_dimensions"] == "2 rows x 1 columns"

    def test_failure_metadata_omits_aliases_and_records_text_only_403(self):
        """Failure metadata omits safe_reason and http_status, has exactly one
        failure-category/basis representation, and for text-only HTTP Error 403
        records unknown + insufficient_structured_evidence + hint 403 + no structured status.
        """
        mock_ticker = MagicMock()
        mock_ticker.get_recommendations.side_effect = Exception("HTTP Error 403: Forbidden")
        mock_factory = MagicMock(return_value=mock_ticker)

        meta = execute_probe("AAPL", "get_recommendations", ticker_factory=mock_factory)

        assert meta["success"] is False
        assert "safe_reason" not in meta
        assert "http_status" not in meta
        assert "failure_category" in meta
        assert "failure_category_basis" in meta
        assert meta["failure_category"] == "unknown"
        assert meta["failure_category_basis"] == "insufficient_structured_evidence"
        assert type(meta["failure_category_basis"]) is str
        assert meta["text_status_hint"] == 403
        assert meta["structured_http_status"] is None
        assert meta["http_status_source"] is None

    def test_metadata_sanitization_against_injected_sentinels(self):
        sentinel_url = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/AAPL?crumb=SENTINEL_CRUMB_ABC"
        sentinel_cookie = "B=SENTINEL_COOKIE_XYZ"
        sentinel_header = "Bearer SENTINEL_AUTH_TOKEN_123"
        sentinel_body = '{"quoteSummary":{"result":[{"financialData":{"currentPrice":999999.88}}]}}'
        sentinel_crumb = "SENTINEL_CRUMB_ABC"
        sentinel_financial = "999999.88"

        error_message = (
            f"Failed request to {sentinel_url} with Cookie: {sentinel_cookie} "
            f"and Authorization: {sentinel_header}. Raw response body: {sentinel_body}"
        )

        mock_ticker = MagicMock()
        mock_ticker.get_info.side_effect = Exception(error_message)
        mock_factory = MagicMock(return_value=mock_ticker)

        meta = execute_probe("AAPL", "get_info", ticker_factory=mock_factory)

        assert meta["success"] is False
        assert meta["exception_class"] == "Exception"
        assert meta["result_dimensions"] == "0 items (error)"
        assert meta["failure_category"] == "unknown"
        assert meta["failure_category_basis"] == "insufficient_structured_evidence"
        assert type(meta["failure_category_basis"]) is str
        assert "safe_reason" not in meta
        assert "http_status" not in meta

        # String representation of metadata must NOT contain any sentinel
        meta_str = str(meta)
        meta_json = json.dumps(meta)

        for representation in (meta_str, meta_json):
            assert sentinel_url not in representation
            assert sentinel_cookie not in representation
            assert sentinel_header not in representation
            assert sentinel_body not in representation
            assert sentinel_crumb not in representation
            assert sentinel_financial not in representation
            assert "Raw response body" not in representation

    def test_metadata_sanitization_on_successful_payload(self):
        mock_ticker = MagicMock()
        mock_ticker.get_info.return_value = {
            "financial_secret": 12345678,
            "secret_crumb": "sensitive_data",
            "netIncome": 99999999,
        }
        mock_factory = MagicMock(return_value=mock_ticker)

        meta = execute_probe("MSFT", "get_info", ticker_factory=mock_factory)

        assert meta["success"] is True
        assert meta["result_dimensions"] == "3 keys"

        meta_str = str(meta)
        assert "financial_secret" not in meta_str
        assert "secret_crumb" not in meta_str
        assert "sensitive_data" not in meta_str
        assert "12345678" not in meta_str
        assert "99999999" not in meta_str


class TestUIProbe:
    def test_initial_render_makes_zero_requests(self):
        """Verify initial render performs zero Yahoo requests and displays default selections."""
        at = AppTest.from_file(PROBE_FILE_PATH).run()

        assert any("Temporary Yahoo Cloud Diagnostic Probe" in t.value for t in at.title)
        assert any("TEMPORARY STANDALONE DIAGNOSTIC ONLY" in w.value for w in at.warning)

        assert len(at.selectbox) >= 2
        symbol_box = at.selectbox[0]
        operation_box = at.selectbox[1]
        assert symbol_box.value == "AAPL"
        assert operation_box.value == "get_recommendations"

        assert len(at.button) >= 1
        assert at.button[0].label == "Run Diagnostic Probe"

        # On initial render, probe results (table / json / errors) must NOT be rendered
        assert len(at.table) == 0
        assert len(at.json) == 0
        assert len(at.error) == 0
        assert len(at.success) == 0

    def test_textual_403_displays_unknown_and_basis_and_text_hint(self, monkeypatch):
        """A textual HTTP Error 403 alone must display category unknown, basis no structured HTTP status, and text hint 403."""
        mock_ticker = MagicMock()
        mock_ticker.get_recommendations.side_effect = Exception("HTTP Error 403: Forbidden")
        monkeypatch.setattr(yf, "Ticker", MagicMock(return_value=mock_ticker))

        at = AppTest.from_file(PROBE_FILE_PATH).run()
        at.button[0].click().run()

        assert len(at.error) == 1
        error_msg = at.error[0].value
        assert "Failure Category: `unknown`" in error_msg
        assert "Category Basis: `no structured HTTP status`" in error_msg
        assert "Text Hint: `403`" in error_msg

        # Table rows check
        assert len(at.table) == 1
        table_df = at.table[0].value
        assert isinstance(table_df, pd.DataFrame)
        fields = dict(zip(table_df["Field"], table_df["Value"]))

        assert fields["Failure Category"] == "unknown"
        assert fields["Category Basis"] == "no structured HTTP status"
        assert fields["Text Status Hint (non-authoritative)"] == "403"
        assert fields["Structured HTTP Status"] == "None"
        assert fields["HTTP Status Source"] == "None"
        assert "HTTP Backend (inferred)" in fields
        assert "curl_cffi.requests Importable" in fields
        assert "YF_DISABLE_CURL_CFFI Enabled" in fields
        assert "YF_DISABLE_CURL_CFFI Set" not in fields
        assert "Safe Reason" not in fields
        assert "HTTP Status" not in fields

        # st.json(metadata) exposes the canonical machine value
        assert len(at.json) == 1
        raw_json_val = at.json[0].value
        json_meta = json.loads(raw_json_val) if isinstance(raw_json_val, str) else raw_json_val
        assert json_meta["failure_category"] == "unknown"
        assert json_meta["failure_category_basis"] == "insufficient_structured_evidence"
        assert type(json_meta["failure_category_basis"]) is str
        assert json_meta["text_status_hint"] == 403
        assert json_meta["structured_http_status"] is None
        assert "safe_reason" not in json_meta
        assert "http_status" not in json_meta
