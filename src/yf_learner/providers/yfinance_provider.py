"""YFinance implementation of MarketDataProvider.

This is the only module in the application permitted to import yfinance.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from yf_learner.providers.errors import ProviderFailureKind, ProviderUpstreamError
from yf_learner.providers.protocol import MarketDataProvider
from yf_learner.providers.raw_models import (
    RawAnalystData,
    RawFundamentalsData,
    RawHistoryData,
    RawNewsData,
    RawQuoteData,
    RawSearchResults,
    RawStatementData,
    RawTable,
)

# Configure network retries and exception visibility once as required by the specification
yf.config.network.retries = 2
yf.config.debug.hide_exceptions = False


def _clean_scalar(val: Any) -> Any:
    """Convert numpy/pandas scalar values to clean standard Python primitives."""
    if val is None:
        return None
    if hasattr(val, "item"):
        val = val.item()
    if isinstance(val, float):
        return None if (math.isnan(val) or math.isinf(val)) else val
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


def _dataframe_to_raw_table(df: Any) -> RawTable:
    """Convert pandas DataFrame to a RawTable using only plain Python primitives."""
    if df is None:
        return RawTable(columns=(), index=(), data=())

    if hasattr(df, "empty") and df.empty:
        return RawTable(columns=(), index=(), data=())

    # Format columns
    columns_list: list[str] = []
    for col in getattr(df, "columns", ()):
        if hasattr(col, "strftime"):
            columns_list.append(col.strftime("%Y-%m-%d"))
        else:
            columns_list.append(str(col))
    columns = tuple(columns_list)

    # Format index
    index_list: list[str] = []
    for idx in getattr(df, "index", ()):
        if hasattr(idx, "strftime"):
            if hasattr(idx, "hour") and (idx.hour or idx.minute or idx.second):
                index_list.append(idx.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                index_list.append(idx.strftime("%Y-%m-%d"))
        else:
            index_list.append(str(idx))
    index = tuple(index_list)

    # Format rows
    rows: list[tuple[Any, ...]] = []
    try:
        it = df.itertuples(index=False, name=None)
    except Exception:
        # Fallback if itertuples is not present on fake/mock objects
        it = [tuple(row) for row in getattr(df, "values", ())]

    for row in it:
        cleaned_row = tuple(_clean_scalar(val) for val in row)
        rows.append(cleaned_row)

    return RawTable(columns=columns, index=index, data=tuple(rows))


def _extract_http_status(exc: BaseException) -> int | None:
    """Extract an HTTP status from public exception attributes only."""
    for obj in (exc, getattr(exc, "response", None)):
        if obj is None:
            continue
        for attr in ("status_code", "code"):
            code = getattr(obj, attr, None)
            if isinstance(code, int) and not isinstance(code, bool) and 100 <= code <= 599:
                return code

    # yfinance commonly surfaces urllib-style errors as ``HTTP Error 401``.
    match = re.search(r"\bHTTP(?:\s+Error)?\s+(\d{3})\b", str(exc), re.IGNORECASE)
    if match:
        code = int(match.group(1))
        if 400 <= code <= 599:
            return code
    return None


def _classify_yfinance_exception(exc: Exception) -> ProviderFailureKind | None:
    """Return a category only for known yfinance/transport failures."""
    http_status = _extract_http_status(exc)
    text = str(exc).lower()
    name = type(exc).__name__.lower()
    module = type(exc).__module__.lower()

    rate_limit_error = getattr(getattr(yf, "exceptions", None), "YFRateLimitError", None)
    if rate_limit_error is not None and isinstance(exc, rate_limit_error):
        return ProviderFailureKind.RATE_LIMITED
    if http_status == 429 or re.search(r"\btoo many requests\b|\brate[- ]limited\b", text):
        return ProviderFailureKind.RATE_LIMITED

    if (
        http_status in (401, 403)
        or "invalid crumb" in text
        or "user is unable to access this feature" in text
        or "unable-to-access-feature" in text
    ):
        return ProviderFailureKind.ACCESS_DENIED

    if (
        isinstance(exc, (TimeoutError, ConnectionError))
        or (http_status is not None and (http_status == 408 or 500 <= http_status <= 599))
        or (
            module.startswith(("yfinance.", "requests.", "urllib3.", "urllib."))
            and name in {
                "yfconnectionerror",
                "yftimeouterror",
                "timeout",
                "readtimeout",
                "connecttimeout",
                "connectionerror",
                "newconnectionerror",
                "maxretryerror",
            }
        )
    ):
        return ProviderFailureKind.UNAVAILABLE

    if isinstance(exc, ValueError) and type(exc).__name__ == "JSONDecodeError":
        return ProviderFailureKind.BAD_RESPONSE
    return None


def _call_yahoo(operation: str, call: Any) -> Any:
    """Call one yfinance operation and expose only typed upstream failures."""
    try:
        return call()
    except ProviderUpstreamError:
        raise
    except Exception as exc:
        kind = _classify_yfinance_exception(exc)
        if kind is None:
            raise
        raise ProviderUpstreamError(kind=kind, operation=operation, http_status=_extract_http_status(exc)) from exc


def _require_mapping(value: Any, operation: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderUpstreamError(kind=ProviderFailureKind.BAD_RESPONSE, operation=operation)
    return value


def _require_dataframe_like(value: Any, operation: str) -> Any:
    if value is None or not hasattr(value, "columns") or not hasattr(value, "index"):
        raise ProviderUpstreamError(kind=ProviderFailureKind.BAD_RESPONSE, operation=operation)
    return value


class YFinanceProvider(MarketDataProvider):
    """Concrete MarketDataProvider backed by yfinance."""

    def __init__(self) -> None:
        # Re-ensure configuration is active
        yf.config.network.retries = 2
        yf.config.debug.hide_exceptions = False

    def search(self, query: str) -> RawSearchResults:
        """Search Yahoo Finance for quotes matching the query."""
        search_obj = yf.Search(
            query,
            max_results=8,
            news_count=0,
            lists_count=0,
            include_cb=False,
            include_nav_links=False,
            include_research=False,
            include_cultural_assets=False,
            recommended=0,
            raise_errors=True,
        )
        quotes = search_obj.quotes or []
        # Ensure at most 8 quotes
        quotes = quotes[:8]
        return RawSearchResults(
            raw_quotes=quotes,
            retrieved_at=datetime.now(timezone.utc),
        )

    def quote(self, symbol: str) -> RawQuoteData:
        """Retrieve fast_info and history_metadata for a fresh ticker."""
        ticker = yf.Ticker(symbol)
        raw_fast_info: dict[str, Any] = {}
        try:
            fi = ticker.get_fast_info()
            if hasattr(fi, "items"):
                for k, v in fi.items():
                    raw_fast_info[str(k)] = _clean_scalar(v)
            elif isinstance(fi, dict):
                for k, v in fi.items():
                    raw_fast_info[str(k)] = _clean_scalar(v)
        except Exception:
            pass

        raw_metadata: dict[str, Any] = {}
        try:
            meta = ticker.get_history_metadata()
            if isinstance(meta, dict):
                for k, v in meta.items():
                    raw_metadata[str(k)] = _clean_scalar(v)
        except Exception:
            pass

        return RawQuoteData(
            symbol=symbol,
            fast_info=raw_fast_info,
            history_metadata=raw_metadata,
            retrieved_at=datetime.now(timezone.utc),
        )

    def history(
        self,
        symbol: str,
        period: str,
        interval: str,
        auto_adjust: bool,
        actions: bool,
    ) -> RawHistoryData:
        """Fetch historical price table for ticker."""
        ticker = yf.Ticker(symbol)
        df = ticker.history(
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            actions=actions,
        )
        table = _dataframe_to_raw_table(df)
        return RawHistoryData(
            symbol=symbol,
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            actions=actions,
            table=table,
            retrieved_at=datetime.now(timezone.utc),
        )

    def fundamentals(self, symbol: str) -> RawFundamentalsData:
        """Fetch company fundamentals dictionary for ticker."""
        ticker = yf.Ticker(symbol)
        info = _require_mapping(_call_yahoo("fundamentals", ticker.get_info), "fundamentals")
        cleaned_info: dict[str, Any] = {str(k): _clean_scalar(v) for k, v in info.items()}

        return RawFundamentalsData(
            symbol=symbol,
            info=cleaned_info,
            retrieved_at=datetime.now(timezone.utc),
        )

    def financial_statement(
        self,
        symbol: str,
        statement: str,
        frequency: str,
    ) -> RawStatementData:
        """Fetch income statement, balance sheet, or cash flow."""
        ticker = yf.Ticker(symbol)
        norm_stmt = statement.strip().lower()

        if norm_stmt in ("income statement", "income", "income_stmt"):
            df = ticker.get_income_stmt(freq=frequency)
        elif norm_stmt in ("balance sheet", "balance_sheet"):
            df = ticker.get_balance_sheet(freq=frequency)
        elif norm_stmt in ("cash flow", "cash_flow"):
            df = ticker.get_cash_flow(freq=frequency)
        else:
            raise ValueError(f"Unsupported financial statement: {statement}")

        table = _dataframe_to_raw_table(df)
        return RawStatementData(
            symbol=symbol,
            statement=statement,
            frequency=frequency,
            table=table,
            retrieved_at=datetime.now(timezone.utc),
        )

    def analyst_data(self, symbol: str, dataset: str) -> RawAnalystData:
        """Fetch analyst recommendations, price targets, or estimates."""
        ticker = yf.Ticker(symbol)
        norm_dataset = dataset.strip().lower()

        table: RawTable | None = None
        targets_dict: dict[str, Any] | None = None

        if norm_dataset == "recommendations":
            df = _require_dataframe_like(_call_yahoo(f"analyst_data:{dataset}", ticker.get_recommendations), f"analyst_data:{dataset}")
            table = _dataframe_to_raw_table(df)

        elif norm_dataset == "price_targets":
            operation = f"analyst_data:{dataset}"
            raw_targets = _call_yahoo(operation, ticker.get_analyst_price_targets)
            if isinstance(raw_targets, Mapping):
                targets_dict = {str(k): _clean_scalar(v) for k, v in raw_targets.items()}
            elif hasattr(raw_targets, "to_dict"):
                try:
                    td = raw_targets.to_dict()
                    if not isinstance(td, Mapping):
                        raise TypeError("price target response is not mapping-shaped")
                    targets_dict = {str(k): _clean_scalar(v) for k, v in td.items()}
                except Exception:
                    raise ProviderUpstreamError(
                        kind=ProviderFailureKind.BAD_RESPONSE,
                        operation=operation,
                    )
            elif hasattr(raw_targets, "columns") and hasattr(raw_targets, "index"):
                table = _dataframe_to_raw_table(raw_targets)
            else:
                raise ProviderUpstreamError(kind=ProviderFailureKind.BAD_RESPONSE, operation=operation)

        elif norm_dataset == "earnings_estimate":
            df = _require_dataframe_like(_call_yahoo(f"analyst_data:{dataset}", ticker.get_earnings_estimate), f"analyst_data:{dataset}")
            table = _dataframe_to_raw_table(df)

        elif norm_dataset == "revenue_estimate":
            df = _require_dataframe_like(_call_yahoo(f"analyst_data:{dataset}", ticker.get_revenue_estimate), f"analyst_data:{dataset}")
            table = _dataframe_to_raw_table(df)

        elif norm_dataset == "growth_estimates":
            df = _require_dataframe_like(_call_yahoo(f"analyst_data:{dataset}", ticker.get_growth_estimates), f"analyst_data:{dataset}")
            table = _dataframe_to_raw_table(df)

        else:
            raise ValueError(f"Unsupported analyst dataset: {dataset}")

        return RawAnalystData(
            symbol=symbol,
            dataset=dataset,
            table=table,
            targets_dict=targets_dict,
            retrieved_at=datetime.now(timezone.utc),
        )

    def news(self, symbol: str, feed: str, count: int) -> RawNewsData:
        """Fetch news articles for symbol."""
        ticker = yf.Ticker(symbol)
        # feeds are: "news", "all", "press releases"
        raw_list = ticker.get_news(count=count, tab=feed)
        cleaned_list: list[dict[str, Any]] = []
        if isinstance(raw_list, list):
            for item in raw_list:
                if isinstance(item, dict):
                    cleaned_item: dict[str, Any] = {}
                    for k, v in item.items():
                        cleaned_item[str(k)] = _clean_scalar(v)
                    cleaned_list.append(cleaned_item)

        return RawNewsData(
            symbol=symbol,
            feed=feed,
            raw_items=cleaned_list,
            retrieved_at=datetime.now(timezone.utc),
        )
