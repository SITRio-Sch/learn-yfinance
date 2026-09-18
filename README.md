# Learn yFinance

An interactive, read-only educational Streamlit workbench designed for nontechnical learners to explore market data workflows and understand how the open-source `yfinance` Python library queries Yahoo Finance.

## Architecture & Boundary Contract

The application enforces a strict boundary:

```text
Streamlit UI  ──>  MarketDataService  ──>  Pure Normalizers  ──>  MarketDataProvider Protocol  ──>  YFinanceProvider  ──>  yfinance
```

- **Strict Import Boundary**: Only `src/yf_learner/providers/yfinance_provider.py` imports `yfinance`. No other application module imports `yfinance` or makes direct Yahoo HTTP requests.
- **Typed Domain Models**: The UI receives typed, immutable (frozen/slotted) domain models (`QuoteSnapshot`, `HistoryResult`, `FundamentalsResult`, `StatementResult`, `AnalystResult`, `NewsResult`) or friendly `DataProblem` objects—never raw Yahoo dictionaries or DataFrames.
- **Pure Normalizers**: Absent values, `None`, `NaN`, `NaT`, and malformed data are normalized to `None` without invented defaults. The UI consistently displays missing values as `Not available`.
- **Thread-Safe Request Gate**: Serializes provider operations with a minimum ~250ms interval between calls to avoid burst rate-limiting.
- **Session-Scoped Caching & Independent Refresh**: Uses `st.cache_data(scope="session")` keyed by independent per-tab integer refresh tokens. Refreshing fetches under a new key and clears prior stale data upon failure.
- **Zero Initial Network Calls**: Initial page load renders the educational overview and performs zero provider requests. Live queries only occur upon explicit user interaction (e.g., submitting search or opening a ticker).
- **Lazy Tab Execution**: Exactly six tabs (`Quote`, `History`, `Fundamentals`, `Financial Statements`, `Analyst Data`, `News`) rendered with Streamlit 1.64.0 `.open` tracking so inactive tabs never trigger fetches.

## Installation & Running

### Requirements
- Python 3.14.7
- Pip

### Setup
Install dependencies in editable development mode:
```bash
python -m pip install -e ".[dev]"
```

### Launch
Start the educational server bound to `http://127.0.0.1:8501`:
```bash
python launcher.py
```

### Running Tests
Execute the complete test suite with network sockets disabled via `pytest-socket`:
```bash
python -m pytest
```

## Educational Features

1. **Search**: Find up to 8 tickers by company name or symbol without auto-triggering details.
2. **Quote**: Inspect real-time/delayed trading metrics (last price, day range, 52-week boundaries, market cap).
3. **History**: Analyze daily, weekly, or monthly historical OHLCV data with interactive charts and auto-adjust options.
4. **Fundamentals**: Explore company profiles, industry categorization, and valuation ratios (P/E, Enterprise Value, Beta).
5. **Financial Statements**: Examine Annual and Quarterly Income Statements, Balance Sheets, and Cash Flow tables.
6. **Analyst Data**: View Wall Street consensus recommendations, price targets, and future growth/earnings estimates.
7. **News**: Read recent news headlines and press releases.
8. **Under the Hood**: Every tab features an explanatory "What yfinance is doing" code expander and strict data provenance details.

## Public deployment

This application is configured for deployment on Streamlit Community Cloud from the public GitHub repository `sitrio-sch/learn-yfinance`.

### Cloud Configuration

When deploying on Streamlit Community Cloud, specify the following fields:
- **Repository**: `sitrio-sch/learn-yfinance`
- **Branch**: `main`
- **Main file path**: `app.py`
- **Python version**: `3.14`
- **App URL**: `https://<chosen-subdomain>.streamlit.app` (placeholder chosen by user)

### Runtime & Access Notes

- **Runtime Versions**: Streamlit Community Cloud installs dependencies directly from `requirements.txt` (`streamlit==1.64.0` and `yfinance==1.7.0`).
- **Secrets & API Keys**: No secrets, credentials, or API keys are required.
- **Data Access & Limitations**: Live read-only market data is retrieved from Yahoo Finance via `yfinance`; standard Yahoo data coverage and rate-limit limitations remain applicable.
- **Sharing**: The app URL is public and can be shared with anyone without requiring viewer login.
