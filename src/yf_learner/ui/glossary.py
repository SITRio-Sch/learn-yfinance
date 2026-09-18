"""Static, beginner-friendly explanations for finance-related UI labels.

The glossary is deliberately independent from Streamlit and from live data.  A
label is explained only when it is a known, stable concept; arbitrary Yahoo
Finance row names return ``None`` rather than receiving an invented definition.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    """One short explanation suitable for a Streamlit help tooltip."""

    label: str
    explanation: str
    example: str | None = None

    def as_help(self) -> str:
        """Return the entry as compact Markdown for Streamlit's ``help=``."""
        if self.example:
            return f"{self.explanation} **Example:** {self.example}"
        return self.explanation


def _key(value: str) -> str:
    """Normalize case, punctuation, spacing, and common label separators."""
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _entry(label: str, explanation: str, example: str | None = None) -> GlossaryEntry:
    return GlossaryEntry(label=label, explanation=explanation, example=example)


GLOSSARY: dict[str, GlossaryEntry] = {
    "Quote Snapshot": _entry(
        "Quote Snapshot",
        "A compact view of a security's latest reported trading information.",
    ),
    "Last Price": _entry(
        "Last Price",
        "The latest reported trading price for one share.",
        "a last price of $190 means the latest reported trade was at $190 per share.",
    ),
    "Previous Close": _entry(
        "Previous Close",
        "The last official closing price from the previous regular trading session.",
        "a previous close of $188 is the reference close used before today's session.",
    ),
    "Open": _entry(
        "Open",
        "The first regular-session trading price for the selected period.",
        "a daily open of $190 is the price at the start of that trading day.",
    ),
    "Day High / Low": _entry(
        "Day High / Low",
        "The highest and lowest reported prices during the current trading day.",
        "$192 / $187 means the price has traded between those values today.",
    ),
    "52-Week Range": _entry(
        "52-Week Range",
        "The highest and lowest reported prices during roughly the last year.",
        "$150–$210 shows the observed low and high over that period.",
    ),
    "Volume": _entry(
        "Volume",
        "The number of shares traded during the selected period.",
        "a volume of 2,000,000 means two million shares changed hands.",
    ),
    "Average Volume": _entry(
        "Average Volume",
        "The average number of shares traded over a stated lookback period.",
        "a 10-day average helps compare today's activity with recent trading activity.",
    ),
    "Market Cap": _entry(
        "Market Cap",
        "The estimated market value of a company's outstanding shares.",
        "1 billion shares at $10 each implies a $10 billion market cap.",
    ),
    "Currency": _entry(
        "Currency",
        "The currency used for the displayed prices and financial amounts.",
        "USD means the values are reported in US dollars.",
    ),
    "Exchange": _entry(
        "Exchange",
        "The marketplace or exchange where the security is listed or traded.",
        "NASDAQ and NYSE are examples of stock exchanges.",
    ),
    "Timezone": _entry(
        "Timezone",
        "The market timezone associated with the quote or trading session.",
        "America/New_York is commonly used for US exchanges.",
    ),
    "Historical Prices & Volume": _entry(
        "Historical Prices & Volume",
        "A time series of past prices and trading activity used to study trends.",
    ),
    "Latest Close": _entry(
        "Latest Close",
        "The closing price at the end of the most recent returned historical period.",
        "the latest daily close is the final Close value in the selected history range.",
    ),
    "High": _entry(
        "High",
        "The highest traded price within one returned period, such as one day.",
    ),
    "Low": _entry(
        "Low",
        "The lowest traded price within one returned period, such as one day.",
    ),
    "Close": _entry(
        "Close",
        "The final reported trading price within one returned period.",
    ),
    "Period": _entry(
        "Period",
        "How far back the history request should look, such as one month or one year.",
        "1y asks yfinance for about one year of history.",
    ),
    "Interval": _entry(
        "Interval",
        "The spacing between historical observations returned by Yahoo Finance.",
        "1d returns daily observations and 1wk returns weekly observations.",
    ),
    "Auto-adjust prices": _entry(
        "Auto-adjust prices",
        "Whether historical prices are adjusted for events such as splits and dividends.",
        "adjusted prices are often easier to compare across a stock split.",
    ),
    "Corporate Actions": _entry(
        "Corporate Actions",
        "Company events that can affect shares or their recorded prices, such as dividends and splits.",
    ),
    "Dividends": _entry(
        "Dividends",
        "Cash distributions a company makes to shareholders, shown for the selected period.",
        "a dividend of $0.25 means $0.25 was distributed per share for that event.",
    ),
    "Stock Splits": _entry(
        "Stock Splits",
        "A change in the number of shares and per-share price that keeps the company's total value broadly unchanged.",
        "a 2-for-1 split gives one holder two shares for each previous share.",
    ),
    "Company Fundamentals": _entry(
        "Company Fundamentals",
        "Descriptive and valuation information about a company's business and financial position.",
    ),
    "Profile & Classification": _entry(
        "Profile & Classification",
        "Basic information describing what a company is, where it operates, and how Yahoo classifies it.",
    ),
    "Quote Type": _entry(
        "Quote Type",
        "The kind of security represented by the quote, such as an equity, ETF, or mutual fund.",
        "EQUITY identifies an ordinary company share rather than an ETF.",
    ),
    "Sector": _entry(
        "Sector",
        "A broad industry grouping assigned to a company.",
        "Technology and Healthcare are examples of sectors.",
    ),
    "Industry": _entry(
        "Industry",
        "A more specific business category within a broad sector.",
        "Consumer Electronics can be an industry within Technology.",
    ),
    "Country": _entry(
        "Country",
        "The country associated with the company's headquarters or primary listing information.",
    ),
    "Employees": _entry(
        "Employees",
        "The reported number of full-time employees at the company.",
    ),
    "Valuation & Financial Ratios": _entry(
        "Valuation & Financial Ratios",
        "Measures that describe company size, valuation, profitability, or risk using market and financial data.",
    ),
    "Enterprise Value": _entry(
        "Enterprise Value",
        "A valuation measure that broadly represents the value of the operating business, including debt and cash effects.",
        "analysts often compare enterprise value with revenue or operating earnings.",
    ),
    "Trailing P/E": _entry(
        "Trailing P/E",
        "A price-to-earnings ratio using earnings from the most recently reported past period.",
        "a P/E of 20 means the share price is 20 times the referenced earnings per share.",
    ),
    "Forward P/E": _entry(
        "Forward P/E",
        "A price-to-earnings ratio using estimated future earnings rather than past earnings.",
        "forward P/E can change when analyst earnings estimates change.",
    ),
    "Price / Book": _entry(
        "Price / Book",
        "A ratio comparing a company's market value with the accounting value of its net assets.",
        "a price-to-book ratio of 3 means the market values the company at about three times book value.",
    ),
    "Dividend Yield": _entry(
        "Dividend Yield",
        "Annual dividends expressed as a percentage of the share price.",
        "a 0.32% yield is about $0.32 of annual dividends per $100 of share value, before other considerations.",
    ),
    "Beta (Volatility)": _entry(
        "Beta (Volatility)",
        "A measure of how much a security's historical price movement has varied relative to a broader market benchmark.",
        "a beta above 1 has historically moved more than the benchmark, but it does not predict future returns.",
    ),
    "Financial Statements": _entry(
        "Financial Statements",
        "Standardized accounting reports used to study a company's performance, resources, obligations, and cash generation.",
    ),
    "Statement": _entry(
        "Statement",
        "The type of financial report to retrieve from Yahoo Finance.",
    ),
    "Frequency": _entry(
        "Frequency",
        "How often the financial figures are grouped, such as annually or quarterly.",
    ),
    "Income Statement": _entry(
        "Income Statement",
        "A report of revenue, expenses, and profit or loss over a period.",
    ),
    "Balance Sheet": _entry(
        "Balance Sheet",
        "A report of assets, liabilities, and shareholders' equity at a point in time.",
    ),
    "Cash Flow": _entry(
        "Cash Flow",
        "A report of cash generated and used by operating, investing, and financing activities.",
    ),
    "Annual": _entry(
        "Annual",
        "Figures grouped over a full financial year.",
    ),
    "Quarterly": _entry(
        "Quarterly",
        "Figures grouped over one financial quarter, usually about three months.",
    ),
    "Reporting Period": _entry(
        "Reporting Period",
        "The date range or accounting period represented by a financial statement column.",
        "a column ending 2025-09-30 contains figures reported through that date.",
    ),
    "Financial Metric": _entry(
        "Financial Metric",
        "A named accounting line item returned by Yahoo Finance, such as revenue or net income.",
    ),
    "Analyst Data & Estimates": _entry(
        "Analyst Data & Estimates",
        "Published analyst opinions and estimates about a company's future performance or valuation.",
    ),
    "Dataset": _entry(
        "Dataset",
        "The specific analyst data operation to request from yfinance.",
    ),
    "Analyst Recommendations": _entry(
        "Analyst Recommendations",
        "Counts or classifications of analyst opinions such as buy, hold, or sell.",
        "a higher Strong Buy count means more analysts gave that rating in the returned period.",
    ),
    "Price Targets": _entry(
        "Price Targets",
        "Analyst estimates of possible future share prices; they are opinions, not guarantees.",
        "a mean target of $210 summarizes the average of the returned analyst targets.",
    ),
    "Current Target": _entry(
        "Current Target",
        "The current share price shown alongside analyst target estimates for comparison.",
    ),
    "Low Target": _entry(
        "Low Target",
        "The lowest analyst price target returned for the selected company.",
    ),
    "Mean Target": _entry(
        "Mean Target",
        "The arithmetic average of the returned analyst price targets.",
    ),
    "Median Target": _entry(
        "Median Target",
        "The middle analyst price target after the returned targets are ordered.",
    ),
    "High Target": _entry(
        "High Target",
        "The highest analyst price target returned for the selected company.",
    ),
    "Earnings Estimates": _entry(
        "Earnings Estimates",
        "Analyst estimates of future earnings for upcoming periods.",
    ),
    "Revenue Estimates": _entry(
        "Revenue Estimates",
        "Analyst estimates of future sales or revenue for upcoming periods.",
    ),
    "Growth Estimates": _entry(
        "Growth Estimates",
        "Analyst estimates describing expected future growth rates or trends.",
    ),
    "Analyst Field": _entry(
        "Analyst Field",
        "A column returned by Yahoo Finance's analyst-data endpoint. The exact meaning depends on the selected dataset.",
    ),
    "News & Corporate Releases": _entry(
        "News & Corporate Releases",
        "Recent publisher articles and company announcements that may provide context for market activity.",
    ),
    "News Feed": _entry(
        "News Feed",
        "The Yahoo Finance news collection to retrieve, such as general news or company press releases.",
    ),
    "Press Releases": _entry(
        "Press Releases",
        "Formal announcements issued by a company or organization.",
    ),
    "Articles Count": _entry(
        "Articles Count",
        "The maximum number of news items requested from Yahoo Finance for the selected feed.",
        "a count of 8 asks yfinance to return up to eight articles.",
    ),
}


# Explicit aliases keep caller labels readable while allowing yfinance-style
# column names and punctuation variants to resolve to the same explanation.
_ALIASES_BY_CANONICAL: dict[str, tuple[str, ...]] = {
    "Average Volume": ("Avg Volume (3M)", "Avg Volume (10D)", "Average Volume (3M)", "Average Volume (10D)"),
    "Open": ("Open Price",),
    "High": ("Day High", "Daily High"),
    "Low": ("Day Low", "Daily Low"),
    "Close": ("Closing Price", "Adjusted Close", "Adj Close"),
    "Corporate Actions": ("Include corporate actions",),
    "Auto-adjust prices": ("Auto-adjust", "Auto Adjust Prices"),
    "Trailing P/E": ("Trailing PE", "TrailingPE", "P/E (Trailing)"),
    "Forward P/E": ("Forward PE", "ForwardPE", "P/E (Forward)"),
    "Price / Book": ("Price to Book", "PriceToBook", "P/B"),
    "Beta (Volatility)": ("Beta",),
    "Analyst Recommendations": ("Recommendations", "Recommendation"),
    "Current Target": ("Current", "Current Price", "Current Price Target"),
    "Low Target": ("Low Price Target",),
    "Mean Target": ("Mean", "Average Target", "Average Price Target"),
    "Median Target": ("Median", "Median Price Target"),
    "High Target": ("High Price Target",),
    "Earnings Estimates": ("Earnings Estimate", "Earnings Estimate Data"),
    "Revenue Estimates": ("Revenue Estimate", "Revenue Estimate Data"),
    "Growth Estimates": ("Growth Estimate", "Growth Estimate Data"),
    "News Feed": ("Feed",),
    "Press Releases": ("press releases", "Corporate Releases"),
    "Strong Buy": ("strongBuy", "StrongBuy"),
    "Strong Sell": ("strongSell", "StrongSell"),
}

# Common recommendation columns are stable enough to explain, while unknown
# Yahoo columns remain intentionally unresolved.
GLOSSARY.update(
    {
        "Strong Buy": _entry("Strong Buy", "The strongest positive analyst rating in a recommendation table."),
        "Buy": _entry("Buy", "A positive analyst rating indicating the analyst expects the security to perform well."),
        "Hold": _entry("Hold", "An analyst rating suggesting the investor may keep the position rather than buy or sell."),
        "Sell": _entry("Sell", "A negative analyst rating indicating the analyst expects weaker performance."),
        "Strong Sell": _entry("Strong Sell", "The strongest negative analyst rating in a recommendation table."),
    }
)

ALIASES: dict[str, str] = {_key(label): label for label in GLOSSARY}
for canonical, aliases in _ALIASES_BY_CANONICAL.items():
    for alias in aliases:
        ALIASES[_key(alias)] = canonical


def get_glossary_entry(label: object) -> GlossaryEntry | None:
    """Return a known glossary entry, or ``None`` for unknown labels."""
    if not isinstance(label, str) or not label.strip():
        return None
    canonical = ALIASES.get(_key(label))
    return GLOSSARY.get(canonical) if canonical else None


def get_help(label: object) -> str | None:
    """Return tooltip Markdown for a known label, otherwise ``None``."""
    entry = get_glossary_entry(label)
    return entry.as_help() if entry else None


__all__ = [
    "ALIASES",
    "GLOSSARY",
    "GlossaryEntry",
    "get_glossary_entry",
    "get_help",
]
