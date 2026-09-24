# Dodl investment dashboard

A static, yfinance-only comparison dashboard for GitHub Pages. Python acquires
history in GitHub Actions; the browser reads the resulting JSON. No Python server,
API key, or live Yahoo request is needed in the browser.

## Controls and calculations

Select several investments, search by name/ticker or category, and toggle a
series with its legend button. Choose a chart range and optionally normalise each
price series to 100 at your reference date. Non-trading dates use the last close
on or before that date, at most seven days earlier. The table shows the actual
reference dates. Missing, future or stale references produce a visible warning.

Price mode uses Yahoo `Close` with `auto_adjust=False`, excluding cash
returns. Yahoo may already adjust historical Close for splits. Raw mode retains
native currencies with separate axes; UK pence are converted to pounds. There is
no FX conversion, so this is not a sterling investor's currency-adjusted return.

Total-return mode uses `100 * Adj Close / reference Adj Close`, relying on
Yahoo's split and distribution adjustments as an approximation of reinvestment.
It always uses an index; switching back restores the price-normalisation setting.
Cash events are **not added again**, which would double-count distributions.
Missing adjusted history is reported rather than replaced with price returns.
Accumulation funds normally retain income within NAV and may report no cash
payouts. Taxes, platform fees and execution costs are excluded. Provider history
and adjustments can be incomplete or revised.

## Investment catalogue

`config/dodl-instruments.json` records the public Dodl range checked on
4 September 2026: 58 shares, 29 themed investments and seven AJ Bell funds.
ETFs, ETCs, bond funds and money-market funds are included. The Pension Builder
is an alias of the Balanced fund, not a duplicate investment. Sources:

- [Dodl shares](https://dodl.co.uk/investments/shares)
- [Dodl themed investments](https://dodl.co.uk/investments/themed)
- [Dodl funds](https://dodl.co.uk/investments/funds)
- [Changes to the range](https://help.dodl.co.uk/en/articles/6934005-how-has-the-investment-range-changed)

91 entries have explicit Yahoo mappings. Powerhouse, Lending way (State Street
global high yield) and Socially responsible UK remain visible but unavailable
until their exact instrument/share class can be verified. Some fund mappings
include a share-class confirmation note. A mapped symbol does not guarantee
Yahoo history exists. Review the catalogue when Dodl changes its range; do not
silently resolve ambiguous names to the first search result or substitute a
US-only bond fund for a global bond fund. Individual bond coupon histories are
not supplied by this dashboard.

## Distribution history

`YFinanceClient.get_actions()` acquires dividends, capital-gains distributions
and splits separately from OHLCV prices. Cash values retain Yahoo's original
quote units (including pence). Dates represent the exchange-local event/ex-date,
encoded as UTC midnight, not an actual payment timestamp. Missing action columns
are unknown (`NaN`/JSON `null`), not zero. Reported zero means no reported event of
that type on that row. The source may revise split-adjusted per-share amounts.

```python
from agentic_data_pipeline.ingestion import YFinanceClient
from agentic_data_pipeline import ParquetStorage

actions = YFinanceClient().get_actions("AAPL", period="max")
ParquetStorage().save_dataset(actions, source="yfinance", dataset="corporate_actions")
```

The build saves per-symbol Parquet and metadata under
`dashboard-dist/datasets/raw/yfinance/corporate_actions/`, plus consolidated
`corporate-actions.csv` and `corporate-actions.json`. The dashboard displays
reported events for visible investments and dates and links both downloads.
JSON includes field availability; consult it before interpreting an empty CSV.

The earlier `get_distributions()` and `update_yfinance_distributions()` APIs
remain available for dividend-only `cash_amount` datasets under
`raw/yfinance/distributions/`. `build_return_history()` remains a separate helper
for explicitly supplied cash flows reinvested at aligned closes. Supply prices
excluding cash adjustments and compatible currency/split units to that helper;
it is not the dashboard's adjusted-close calculation.

## Build and test

```bash
uv sync --dev
uv run python -m agentic_data_pipeline.dashboard --output dashboard-dist
python -m http.server --directory dashboard-dist 8000
```

The builder requests ten years of daily data. `--catalogue` and `--assets`
accept alternate paths. `--previous dashboard-cache/prices.json` enables
last-good-history reuse, explicitly labelled stale if a refresh fails. Yahoo
rate limiting stops further requests. A wholly empty build fails without
publishing a blank dashboard; `refresh-status.json` identifies affected symbols.
Saved data may be old even after a successful build; the UI shows observation
dates and warns about selected histories ending more than seven days ago.

```bash
uv run pytest -m 'not integration'
npm ci --prefix dashboard --ignore-scripts
npm test --prefix dashboard
```

Python produces the existing Cobertura XML, JSON and HTML coverage reports.
JavaScript tests cover calculations and DOM controls with Node coverage. The
85% line and 85% branch targets remain separate development targets.

## GitHub Pages

`.github/workflows/dashboard.yml` validates PRs offline, builds a downloadable
`market-dashboard` artifact on pushes, and refreshes on weekdays at 23:17 UTC
or manual dispatch. Only `main` updates the saved snapshot or deploys Pages.

After merging, set repository **Settings → Pages → Source → GitHub Actions**,
and set the Actions repository variable **ENABLE_DASHBOARD_PAGES** to `true`.
Then run **Market dashboard** from the Actions tab. These repository settings
must be enabled by an administrator; adding the workflow does not enable Pages.
The deployment job reports the live URL. Leave the variable unset to build
artifacts without publishing. This workflow needs no market-data secrets.
