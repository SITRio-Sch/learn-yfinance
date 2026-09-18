"""YFinance implementation of MarketDataProvider.

This is the only module in the application permitted to import yfinance.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

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

# Configure network retries once as required by the specification
yf.config.network.retries = 2


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


class YFinanceProvider(MarketDataProvider):
    """Concrete MarketDataProvider backed by yfinance."""

    def __init__(self) -> None:
        # Re-ensure configuration is active
        yf.config.network.retries = 2

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
        info = ticker.get_info()
        cleaned_info: dict[str, Any] = {}
        if isinstance(info, dict):
            for k, v in info.items():
                cleaned_info[str(k)] = _clean_scalar(v)

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
            df = ticker.get_recommendations()
            table = _dataframe_to_raw_table(df)
        elif norm_dataset == "price_targets":
            raw_targets = ticker.get_analyst_price_targets()
            if isinstance(raw_targets, dict):
                targets_dict = {str(k): _clean_scalar(v) for k, v in raw_targets.items()}
            elif hasattr(raw_targets, "to_dict"):
                try:
                    td = raw_targets.to_dict()
                    targets_dict = {str(k): _clean_scalar(v) for k, v in td.items()}
                except Exception:
                    table = _dataframe_to_raw_table(raw_targets)
            else:
                table = _dataframe_to_raw_table(raw_targets)
        elif norm_dataset == "earnings_estimate":
            df = ticker.get_earnings_estimate()
            table = _dataframe_to_raw_table(df)
        elif norm_dataset == "revenue_estimate":
            df = ticker.get_revenue_estimate()
            table = _dataframe_to_raw_table(df)
        elif norm_dataset == "growth_estimates":
            df = ticker.get_growth_estimates()
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
