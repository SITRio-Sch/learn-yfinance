"""Teaching copy, code snippets, and provenance helpers for each topic."""

from __future__ import annotations

from datetime import datetime, timezone

from yf_learner.domain.models import Provenance

TEACHING_COPY = {
    "quote": (
        "A stock quote provides a real-time or delayed snapshot of an instrument's current trading activity. "
        "It includes pricing metrics like the latest traded price, daily bid/ask range, 52-week boundaries, and trading volume. "
        "Learners use quotes to inspect basic market liquidity and valuation before diving deeper into historical trends or fundamentals."
    ),
    "history": (
        "Historical price data captures time-series records of Open, High, Low, Close, and Volume (OHLCV) over specific intervals. "
        "Adjusted prices account for corporate actions such as stock splits and cash dividends, giving an accurate picture of total return. "
        "In quantitative finance and data science, historical series are the foundation for technical analysis, charting, and backtesting."
    ),
    "fundamentals": (
        "Fundamental data reflects a company's underlying business characteristics, capital structure, and valuation metrics. "
        "This includes quantitative ratios like Price-to-Earnings (P/E), Enterprise Value, Price-to-Book, and Dividend Yield, alongside company sector and description. "
        "Fundamental analysts evaluate these figures to determine if a security is undervalued or overvalued relative to its peers."
    ),
    "statements": (
        "Financial statements provide standardized accounting records of a firm's operational performance and financial health. "
        "The Income Statement tracks revenues and expenses, the Balance Sheet lists assets and liabilities, and the Cash Flow statement monitors cash generation. "
        "Comparing annual and quarterly periods reveals long-term trends, working capital stability, and earnings quality."
    ),
    "analyst": (
        "Analyst consensus data compiles recommendations, price targets, and forward-looking growth and earnings estimates from Wall Street research firms. "
        "These figures represent expectations rather than realized performance, indicating how institutional analysts foresee future quarters. "
        "Comparing price targets against current quotes helps understand market sentiment and divergence in valuation perspectives."
    ),
    "news": (
        "Market news feeds provide real-time headlines, press releases, and corporate announcements related to the company. "
        "News sentiment often drives short-term price movements and offers immediate context for sudden shifts in volume or volatility. "
        "Studying news feeds helps learners observe how market participants react to qualitative information."
    ),
}

CODE_SNIPPETS = {
    "quote": """import yfinance as yf

# Instantiate a ticker object for the security
ticker = yf.Ticker("{symbol}")

# FastInfo provides low-latency key market pricing fields
fast_info = ticker.get_fast_info()
last_price = fast_info.last_price
previous_close = fast_info.previous_close

# History metadata provides exchange details and market timestamps
metadata = ticker.get_history_metadata()
exchange = metadata.get("exchangeName")
currency = metadata.get("currency")
""",
    "history": """import yfinance as yf

ticker = yf.Ticker("{symbol}")

# Retrieve historical time series with chosen period and interval
# auto_adjust=True adjusts Open, High, Low, Close for splits and dividends
history_df = ticker.history(
    period="{period}",
    interval="{interval}",
    auto_adjust={auto_adjust},
    actions={actions}
)
""",
    "fundamentals": """import yfinance as yf

ticker = yf.Ticker("{symbol}")

# get_info() retrieves fundamental properties and valuation ratios
info = ticker.get_info()
name = info.get("shortName")
market_cap = info.get("marketCap")
pe_ratio = info.get("trailingPE")
summary = info.get("longBusinessSummary")
""",
    "statements": """import yfinance as yf

ticker = yf.Ticker("{symbol}")

# Financial statements can be requested for yearly or quarterly periods:
# - ticker.get_income_stmt(freq="{freq}")
# - ticker.get_balance_sheet(freq="{freq}")
# - ticker.get_cash_flow(freq="{freq}")
statement_df = ticker.{method}(freq="{freq}")
""",
    "analyst": """import yfinance as yf

ticker = yf.Ticker("{symbol}")

# Analyst data is retrieved using specialized ticker methods:
# - recommendations: ticker.get_recommendations()
# - price targets: ticker.get_analyst_price_targets()
# - earnings estimates: ticker.get_earnings_estimate()
# - revenue estimates: ticker.get_revenue_estimate()
# - growth estimates: ticker.get_growth_estimates()
data = ticker.{method}()
""",
    "news": """import yfinance as yf

ticker = yf.Ticker("{symbol}")

# Retrieve news articles for a specific feed tab: "news", "all", or "press releases"
news_items = ticker.get_news(count={count}, tab="{feed}")
for item in news_items:
    content = item.get("content", item)
    print(content.get("title"), content.get("pubDate"))
""",
}

LIMITATIONS_NOTES = {
    "quote": "Yahoo Finance quote data may be delayed by 15-20 minutes depending on the exchange. Some international or OTC symbols may lack full volume or aftermarket data.",
    "history": "Historical data is subject to retrospective revisions by Yahoo. Data for older dates or smaller foreign listings may contain intermittent gaps or unadjusted splits.",
    "fundamentals": "Fundamental metrics are scraped from Yahoo's profile and key statistics pages and can lag official SEC filings or quarterly earnings releases by several days.",
    "statements": "Financial statement figures are derived from standard Yahoo accounting schemas, which may aggregate or categorize certain line items differently than primary GAAP/IFRS filings.",
    "analyst": "Analyst consensus figures depend on coverage. Small-cap or non-US securities may have zero or outdated analyst estimates.",
    "news": "News feeds reflect Yahoo's curated publisher aggregation. Articles may include sponsored content or third-party syndications with varying update frequencies.",
}


def format_provenance_markdown(prov: Provenance | None, limitation_key: str | None = None) -> str:
    """Render standardized markdown for provenance and limitations."""
    if prov is None:
        source_str = "Yahoo Finance via yfinance"
        attempt_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        retrieved_str = "Not available"
        as_of_str = "Not available"
    else:
        source_str = prov.source
        attempt_str = None
        retrieved_str = prov.retrieved_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        if prov.data_as_of is not None:
            if isinstance(prov.data_as_of, datetime):
                as_of_str = prov.data_as_of.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            else:
                as_of_str = str(prov.data_as_of)
        else:
            as_of_str = "Not available"

    retrieval_line = f"- Retrieval attempt: `{attempt_str}`\n" if attempt_str else ""
    lines = [
        "---",
        (
            "**Provenance:**\n"
            f"- Source: `{source_str}`\n"
            f"{retrieval_line}"
            f"- Retrieved: `{retrieved_str}`\n"
            f"- Data as of: `{as_of_str}`"
        ),
    ]
    if limitation_key and limitation_key in LIMITATIONS_NOTES:
        lines.append(f"**Data Limitations:** {LIMITATIONS_NOTES[limitation_key]}")

    return "\n\n".join(lines)
