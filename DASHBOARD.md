# Investment return dashboard

The repository includes a static dashboard designed for GitHub Pages. It compares
historical returns for investments in the public AJ Bell Dodl range using
yfinance data.

## What it shows

The dashboard can plot several instruments on one chart, turn individual series
on or off, switch between **price** and **total return**, and optionally
normalise every visible series to 100 on a selected date.

Price mode uses unadjusted closing prices. Total-return mode combines those
prices with explicit historical cash distributions and assumes each
distribution is reinvested at the closing price on the aligned payment/ex-date.
This makes the cash-return contribution visible and keeps it separate from the
OHLCV price dataset.

## Distribution dataset

`YFinanceClient.get_distributions()` returns a UTC-indexed DataFrame with:

| column | meaning |
| --- | --- |
| `cash_amount` | cash paid per share/unit |
| `source` | `yfinance` |

The incremental persistence helper is:

```python
from agentic_data_pipeline import update_yfinance_distributions

frame = update_yfinance_distributions("VHYL.L")
```

It stores data at:

```text
data/raw/yfinance/distributions/VHYL.L.parquet
data/raw/yfinance/distributions/VHYL.L.metadata.json
```

A valid empty dataset represents an instrument with no recorded distributions.

## Dodl universe

`scripts/build_dashboard.py` discovers the current public Dodl investment range
from the Dodl shares, themed-investments and funds pages each time the site is
built. Names are resolved to Yahoo Finance symbols using `yfinance.Search`.

This keeps the range maintainable as Dodl changes it. Resolution is deliberately
best-effort because some funds may not have a Yahoo Finance listing or may have
ambiguous names. The generated JSON records unresolved instruments and the UI
shows the unresolved count instead of silently pretending the range is
complete.

## Build locally

```bash
uv sync
uv run python scripts/build_dashboard.py --output site --period 5y
python -m http.server -d site 8000
```

Then open `http://localhost:8000`.

## GitHub Pages

`.github/workflows/dashboard.yml` rebuilds on weekdays, on manual dispatch, and
when dashboard-related files change on `main`. It publishes the generated
`site/` directory using GitHub Pages Actions.

Repository Pages settings must allow **GitHub Actions** as the deployment
source. No API key is required: both Dodl discovery and yfinance use public
endpoints.

## Return calculation

For each market observation after the first, the total-return period return is:

```text
(close_t + cash_distribution_t) / close_(t-1) - 1
```

The series is compounded from a base of 100. This is a comparison tool, not a
tax- or execution-accurate account statement: it does not model withholding
tax, platform fees, dealing costs, FX costs or reinvestment slippage.
