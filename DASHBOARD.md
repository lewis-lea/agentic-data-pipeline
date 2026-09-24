# Simulated company dashboard

The public GitHub Pages build uses **fictional, reproducible price and dividend
histories**. No Yahoo prices are downloaded, fitted, cached or included in that
build. All company names and ticker symbols are fictional.
A separate explicit Yahoo mode remains available for local research.

## Synthetic dataset

`src/agentic_data_pipeline/synthetic.py` generates more than 2,500 weekday
observations per example, from 4 January 2016 to 31 December 2025, in GBP.

| Example | Authored scenario |
| --- | --- |
| Simulated Company A | Expansion, a sharp shared downturn, recovery and a later pullback |
| Simulated Company B | Cyclical growth and larger cash distributions |
| Simulated Company C | Stronger long-term growth with technology-like volatility |
| Simulated Company D | Long-term decline followed by a partial recovery |
| Simulated Company E | Cyclical growth followed by a sustained weaker period |
| Simulated Company F | Growth followed by a flatter period |

These broad trend shapes are hand-authored assumptions, **not a numerical fit
or a claim about the companies' historical returns**. Starting levels, annual
trend anchors, yields and volatility parameters are documented in `PROFILES`.
The generator combines those trends with shared and stock-specific mean-reverting
noise, an abrupt 2020-like shock/recovery and a broader 2022-like drawdown.

The default seed is `2502026`; use `--seed` to produce a different realisation.
Histories are repeatable for the same generator version, seed and dependency
versions. Build timestamps can differ. Per-symbol random streams are stable
when profiles are reordered. Parameters and seed travel with `prices.json` and
the events JSON. This is demonstration data, not a forecasting model.

The simplified calendar excludes weekends but includes exchange holidays.
There are two fictional cash distributions per year on the first weekday on or
after 15 May and 15 November, suspended in 2020. No actual payout dates, special
dividends, capital-gain distributions or splits are reproduced. Price drops by
the cash amount on each simulated ex-date. No splits are simulated.

## Controls and calculations

Select stocks, search by name/ticker, and hide/show each series using its legend.
Choose the chart range and optionally rebase prices to 100 on a reference date.
Non-trading reference dates use the preceding observation, up to seven days
earlier. Actual reference dates are shown in the comparison table.

Simulated total returns reinvest fictional dividends at the ex-date close:

```text
wealth[t] / wealth[t-1] = (price[t] + dividend[t]) / price[t-1]
adjusted_close[t] = wealth[t] / wealth[last] * price[last]
index[t] = 100 * adjusted_close[t] / adjusted_close[reference]
```

The adjusted series is compatible with the chart's existing total-return mode.
Cash is not added twice. Taxes, fees, FX changes and reinvestment slippage are
excluded. The banner, chart watermark, freshness text and event descriptions
identify synthetic mode, including when the chart is exported as an SVG.

## Exports and provenance

The build writes `prices.json`, `corporate-actions.csv`, `corporate-actions.json`
and Parquet/metadata under `datasets/raw/synthetic/corporate_actions/`.
Each snapshot and instrument, each CSV event and each Parquet metadata sidecar
carries a synthetic flag/source. The JSON downloads carry simulation parameters
or generator details; full assumptions remain in `synthetic.py`. Event amounts
are fictional GBP per share, with fictional ex-dates, not actual payment dates.
The SIM-A through SIM-F identifiers are fictional, not exchange tickers.

The builder rejects mixing real and synthetic output directories and rejects
`--previous` in synthetic mode. Use a fresh directory when changing sources.
GitHub Actions never restores old Yahoo caches for public builds and verifies
synthetic provenance before uploading the site.

## Catalogue

`config/simulated-companies.json` defines Simulated Company A through F, using
fictional identifiers `SIM-A` through `SIM-F`. No company profiles, issuer URLs,
real tickers or index-membership claims are included in the public catalogue.
The six scenarios illustrate different growth, decline and cash-yield patterns.
Rebuilding replaces the generated corporate-action files, removing exports for
identities that are no longer in the catalogue.

## Build and test

```bash
uv sync --dev
uv run python -m agentic_data_pipeline.dashboard --data-source synthetic
python -m http.server --directory dashboard-dist 8000
```

Synthetic is also the default when `--data-source` is omitted. Once dependencies
are installed, building requires no network access, credentials or market data.
`--catalogue` and `--assets` accept alternate paths; every synthetic catalogue
symbol must have an authored profile or the build fails.

```bash
uv run pytest -m 'not integration'
npm ci --prefix dashboard --ignore-scripts
npm test --prefix dashboard
```

Tests cover repeatability, distinct seeds, shared downturns, dividend suspensions,
price/total-return consistency, offline generation, exported provenance, source
separation and dashboard controls. Existing coverage reporting remains enabled.

## Local Yahoo research mode

```bash
uv run python -m agentic_data_pipeline.dashboard --data-source yahoo --catalogue path/to/your-real-instruments.json
python -m http.server --directory dashboard-local 8000
```

Yahoo mode requires an explicit catalogue with real symbols; it never uses the
fictional default catalogue. Use the same catalogue schema (checked_at, sources,
and instruments with unique id, name, symbol and category fields).

This explicitly downloads ten years of daily Yahoo histories, and defaults to
`dashboard-local` rather than the public build directory. Optional
`--previous dashboard-local/prices.json` retains last-good histories, visibly
marked stale when a refresh fails. Yahoo mode uses Close for prices and Adj Close
for total returns, with original reported cash units retained in event exports
under `datasets/raw/yfinance/corporate_actions/`. Pence prices convert to GBP;
there is no FX conversion. The existing `get_actions()`, `get_distributions()`
and incremental-ingestion APIs remain available independently.

Yahoo data use and redistribution remain subject to provider terms. The code
licence does not license third-party data. Public publishing uses synthetic mode.

## GitHub Pages

`.github/workflows/dashboard.yml` tests PRs and builds a synthetic
`market-dashboard` artifact on pushes or manual dispatch. Scheduled market-data
refreshes and Yahoo-cache reuse have been removed; this fixture has a fixed
historical period. Only `main` can deploy Pages.

After merging, set **Settings → Pages → Source → GitHub Actions** and the Actions
repository variable **ENABLE_DASHBOARD_PAGES** to `true`. Run **Market dashboard**
from Actions. The deployment job reports the live URL. With the variable unset,
the workflow builds an artifact without publishing. No market-data secrets are
required, and this change does not enable repository deployment settings.
