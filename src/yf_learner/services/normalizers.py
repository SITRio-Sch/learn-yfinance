"""Pure, deterministic normalizers converting raw data into typed domain models."""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any

from yf_learner.domain.models import (
    AnalystPriceTargets,
    AnalystResult,
    FundamentalsResult,
    HistoryPoint,
    HistoryResult,
    NewsItem,
    NewsResult,
    Provenance,
    QuoteSnapshot,
    SearchResultItem,
    SearchResults,
    StatementResult,
    TableData,
)
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

SOURCE_NAME = "Yahoo Finance via yfinance"


def clean_str(val: Any) -> str | None:
    """Clean and strip string, returning None for empty or null-like markers."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null", "nat", "undefined"):
        return None
    return s


def clean_float(val: Any) -> float | None:
    """Safely parse float without invented values."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    try:
        s = str(val).strip().replace(",", "")
        if s.lower() in ("nan", "none", "null", "nat", ""):
            return None
        f = float(s)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def clean_int(val: Any) -> int | None:
    """Safely parse integer without invented values."""
    f = clean_float(val)
    if f is None:
        return None
    try:
        return int(round(f))
    except (ValueError, TypeError, OverflowError):
        return None


def clean_datetime(val: Any) -> datetime | None:
    """Safely parse datetime to UTC without invented values."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day, tzinfo=timezone.utc)
    if isinstance(val, (int, float)):
        # Could be epoch seconds or epoch milliseconds
        try:
            ts = float(val)
            if ts > 1e11:  # milliseconds
                ts /= 1000.0
            if ts <= 0:
                return None
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(val, str):
        s = val.strip()
        if not s or s.lower() in ("nan", "none", "null", "nat"):
            return None
        # Try ISO format
        for fmt in (
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(s, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


def normalize_search(raw: RawSearchResults, query: str) -> SearchResults:
    """Normalize raw search quotes into at most 8 SearchResultItems."""
    items: list[SearchResultItem] = []
    for item in raw.raw_quotes[:8]:
        if not isinstance(item, dict):
            continue
        symbol = clean_str(item.get("symbol"))
        if not symbol:
            continue
        name = clean_str(item.get("shortname") or item.get("longname") or item.get("name"))
        exchange = clean_str(item.get("exchange") or item.get("exchDisp"))
        quote_type = clean_str(item.get("quoteType") or item.get("typeDisp"))
        items.append(
            SearchResultItem(
                symbol=symbol,
                name=name,
                exchange=exchange,
                quote_type=quote_type,
            )
        )

    provenance = Provenance(
        source=SOURCE_NAME,
        retrieved_at=raw.retrieved_at,
        data_as_of=None,
    )
    return SearchResults(
        query=query,
        items=tuple(items),
        provenance=provenance,
    )


def normalize_quote(raw: RawQuoteData) -> QuoteSnapshot:
    """Normalize raw fast_info and history_metadata into QuoteSnapshot."""
    fi = raw.fast_info or {}
    meta = raw.history_metadata or {}

    last_price = clean_float(fi.get("last_price") or fi.get("lastPrice") or meta.get("regularMarketPrice"))
    previous_close = clean_float(
        fi.get("previous_close")
        or fi.get("previousClose")
        or fi.get("regular_market_previous_close")
        or meta.get("regularMarketPreviousClose")
    )
    open_price = clean_float(fi.get("open") or meta.get("regularMarketOpen"))
    day_high = clean_float(fi.get("day_high") or fi.get("dayHigh") or meta.get("regularMarketDayHigh"))
    day_low = clean_float(fi.get("day_low") or fi.get("dayLow") or meta.get("regularMarketDayLow"))
    fifty_two_week_high = clean_float(
        fi.get("year_high")
        or fi.get("yearHigh")
        or fi.get("fiftyTwoWeekHigh")
        or meta.get("fiftyTwoWeekHigh")
    )
    fifty_two_week_low = clean_float(
        fi.get("year_low")
        or fi.get("yearLow")
        or fi.get("fiftyTwoWeekLow")
        or meta.get("fiftyTwoWeekLow")
    )
    volume = clean_int(
        fi.get("last_volume")
        or fi.get("lastVolume")
        or meta.get("regularMarketVolume")
    )
    average_volume = clean_int(
        fi.get("three_month_average_volume")
        or fi.get("threeMonthAverageVolume")
        or meta.get("averageDailyVolume3Month")
    )
    average_volume_10d = clean_int(
        fi.get("ten_day_average_volume")
        or fi.get("tenDayAverageVolume")
        or meta.get("averageDailyVolume10Day")
    )
    currency = clean_str(fi.get("currency") or meta.get("currency"))
    exchange = clean_str(fi.get("exchange") or meta.get("exchangeName") or meta.get("exchange"))
    tz = clean_str(fi.get("timezone") or meta.get("timezone") or meta.get("exchangeTimezoneName"))
    market_cap = clean_float(fi.get("market_cap") or fi.get("marketCap"))

    # Determine data as of timestamp
    data_as_of = None
    market_time = meta.get("regularMarketTime") or fi.get("regularMarketTime")
    if market_time is not None:
        data_as_of = clean_datetime(market_time)

    provenance = Provenance(
        source=SOURCE_NAME,
        retrieved_at=raw.retrieved_at,
        data_as_of=data_as_of,
    )

    return QuoteSnapshot(
        symbol=raw.symbol,
        last_price=last_price,
        previous_close=previous_close,
        open_price=open_price,
        day_high=day_high,
        day_low=day_low,
        fifty_two_week_high=fifty_two_week_high,
        fifty_two_week_low=fifty_two_week_low,
        volume=volume,
        average_volume=average_volume,
        average_volume_10d=average_volume_10d,
        currency=currency,
        exchange=exchange,
        timezone=tz,
        market_cap=market_cap,
        provenance=provenance,
    )


def normalize_history(raw: RawHistoryData) -> HistoryResult:
    """Normalize raw history table into HistoryResult with points."""
    tbl = raw.table
    col_map: dict[str, int] = {}
    for idx, col in enumerate(tbl.columns):
        norm_col = str(col).strip().lower().replace(" ", "")
        col_map[norm_col] = idx

    points: list[HistoryPoint] = []
    newest_as_of: datetime | None = None

    for r_idx, row_label in enumerate(tbl.index):
        row_data = tbl.data[r_idx] if r_idx < len(tbl.data) else ()

        def get_val(key_fragment: str) -> Any:
            for k, col_i in col_map.items():
                if key_fragment in k:
                    if col_i < len(row_data):
                        return row_data[col_i]
            return None

        open_val = clean_float(get_val("open"))
        high_val = clean_float(get_val("high"))
        low_val = clean_float(get_val("low"))
        close_val = clean_float(get_val("close"))
        volume_val = clean_int(get_val("volume"))
        div_val = clean_float(get_val("dividends") or get_val("dividend"))
        splits_val = clean_float(get_val("split") or get_val("stocksplits"))

        clean_time_str = clean_str(row_label) or ""
        point = HistoryPoint(
            date_or_time=clean_time_str,
            open=open_val,
            high=high_val,
            low=low_val,
            close=close_val,
            volume=volume_val,
            dividends=div_val,
            stock_splits=splits_val,
        )
        points.append(point)

        dt = clean_datetime(row_label)
        if dt is not None:
            if newest_as_of is None or dt > newest_as_of:
                newest_as_of = dt

    provenance = Provenance(
        source=SOURCE_NAME,
        retrieved_at=raw.retrieved_at,
        data_as_of=newest_as_of,
    )

    return HistoryResult(
        symbol=raw.symbol,
        period=raw.period,
        interval=raw.interval,
        auto_adjust=raw.auto_adjust,
        actions=raw.actions,
        points=tuple(points),
        provenance=provenance,
    )


def normalize_fundamentals(raw: RawFundamentalsData) -> FundamentalsResult:
    """Normalize raw company info dictionary into FundamentalsResult."""
    info = raw.info or {}

    name = clean_str(info.get("shortName") or info.get("longName"))
    quote_type = clean_str(info.get("quoteType"))
    exchange = clean_str(info.get("exchange"))
    currency = clean_str(info.get("currency") or info.get("financialCurrency"))
    sector = clean_str(info.get("sector"))
    industry = clean_str(info.get("industry"))
    country = clean_str(info.get("country"))
    website = clean_str(info.get("website"))
    employees = clean_int(info.get("fullTimeEmployees"))
    market_cap = clean_float(info.get("marketCap"))
    enterprise_value = clean_float(info.get("enterpriseValue"))
    trailing_pe = clean_float(info.get("trailingPE"))
    forward_pe = clean_float(info.get("forwardPE"))
    price_to_book = clean_float(info.get("priceToBook"))
    dividend_yield = clean_float(info.get("dividendYield"))
    beta = clean_float(info.get("beta"))
    business_summary = clean_str(info.get("longBusinessSummary"))

    # Fundamentals typically do not have a single exact timestamp, but check potential keys
    as_of = None
    for k in ("mostRecentQuarter", "lastFiscalYearEnd", "regularMarketTime"):
        if info.get(k) is not None:
            dt = clean_datetime(info.get(k))
            if dt is not None:
                as_of = dt
                break

    provenance = Provenance(
        source=SOURCE_NAME,
        retrieved_at=raw.retrieved_at,
        data_as_of=as_of,
    )

    return FundamentalsResult(
        symbol=raw.symbol,
        name=name,
        quote_type=quote_type,
        exchange=exchange,
        currency=currency,
        sector=sector,
        industry=industry,
        country=country,
        website=website,
        employees=employees,
        market_cap=market_cap,
        enterprise_value=enterprise_value,
        trailing_pe=trailing_pe,
        forward_pe=forward_pe,
        price_to_book=price_to_book,
        dividend_yield=dividend_yield,
        beta=beta,
        business_summary=business_summary,
        provenance=provenance,
    )


def normalize_statement(raw: RawStatementData) -> StatementResult:
    """Normalize raw statement table into StatementResult."""
    tbl = raw.table

    columns: list[str] = [str(c) for c in tbl.columns]
    index: list[str] = [str(i) for i in tbl.index]

    rows: list[tuple[object | None, ...]] = []
    for r in tbl.data:
        cleaned_row = tuple(
            clean_float(v) if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).isdigit()) else clean_str(v)
            for v in r
        )
        rows.append(cleaned_row)

    # Derive newest date from columns (e.g. 2023-09-30)
    newest_as_of: datetime | None = None
    for col in columns:
        dt = clean_datetime(col)
        if dt is not None:
            if newest_as_of is None or dt > newest_as_of:
                newest_as_of = dt

    table_data = TableData(
        columns=tuple(columns),
        index=tuple(index),
        rows=tuple(rows),
    )

    provenance = Provenance(
        source=SOURCE_NAME,
        retrieved_at=raw.retrieved_at,
        data_as_of=newest_as_of,
    )

    return StatementResult(
        symbol=raw.symbol,
        statement_type=raw.statement,
        frequency=raw.frequency,
        table=table_data,
        provenance=provenance,
    )


def normalize_analyst(raw: RawAnalystData) -> AnalystResult:
    """Normalize raw analyst dataset into AnalystResult."""
    table_data: TableData | None = None
    targets: AnalystPriceTargets | None = None

    if raw.targets_dict is not None:
        targets = AnalystPriceTargets(
            current=clean_float(raw.targets_dict.get("current")),
            low=clean_float(raw.targets_dict.get("low")),
            high=clean_float(raw.targets_dict.get("high")),
            mean=clean_float(raw.targets_dict.get("mean")),
            median=clean_float(raw.targets_dict.get("median")),
        )

    if raw.table is not None:
        columns = tuple(str(c) for c in raw.table.columns)
        index = tuple(str(i) for i in raw.table.index)
        rows: list[tuple[object | None, ...]] = []
        for r in raw.table.data:
            cleaned_row = tuple(
                clean_float(v) if isinstance(v, (int, float)) else clean_str(v)
                for v in r
            )
            rows.append(cleaned_row)
        table_data = TableData(columns=columns, index=index, rows=tuple(rows))

    provenance = Provenance(
        source=SOURCE_NAME,
        retrieved_at=raw.retrieved_at,
        data_as_of=None,
    )

    return AnalystResult(
        symbol=raw.symbol,
        dataset_type=raw.dataset,
        table=table_data,
        targets=targets,
        provenance=provenance,
    )


def normalize_news(raw: RawNewsData) -> NewsResult:
    """Normalize raw news articles list into NewsResult."""
    items: list[NewsItem] = []
    newest_as_of: datetime | None = None

    for raw_item in raw.raw_items:
        if not isinstance(raw_item, dict):
            continue

        # Check nested "content" dictionary or root keys
        content = raw_item.get("content") if isinstance(raw_item.get("content"), dict) else raw_item

        title = clean_str(content.get("title"))
        if not title:
            continue

        # Publisher
        publisher = None
        if isinstance(content.get("provider"), dict):
            publisher = clean_str(content.get("provider", {}).get("displayName"))
        if not publisher:
            publisher = clean_str(content.get("publisher"))

        # Link
        link = None
        if isinstance(content.get("canonicalUrl"), dict):
            link = clean_str(content.get("canonicalUrl", {}).get("url"))
        elif isinstance(content.get("clickThroughUrl"), dict):
            link = clean_str(content.get("clickThroughUrl", {}).get("url"))
        if not link:
            link = clean_str(content.get("link"))

        # Published time
        pub_time = (
            content.get("pubDate")
            or content.get("providerPublishTime")
            or content.get("publishedAt")
            or raw_item.get("providerPublishTime")
        )
        published_at = clean_datetime(pub_time)
        if published_at is not None:
            if newest_as_of is None or published_at > newest_as_of:
                newest_as_of = published_at

        uuid = clean_str(content.get("id") or content.get("uuid") or raw_item.get("uuid"))

        items.append(
            NewsItem(
                title=title,
                publisher=publisher,
                link=link,
                published_at=published_at,
                uuid=uuid,
            )
        )

    provenance = Provenance(
        source=SOURCE_NAME,
        retrieved_at=raw.retrieved_at,
        data_as_of=newest_as_of,
    )

    return NewsResult(
        symbol=raw.symbol,
        feed=raw.feed,
        items=tuple(items),
        provenance=provenance,
    )
