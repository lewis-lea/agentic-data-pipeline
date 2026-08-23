# Agentic Data Pipeline

Reusable ingestion, cleaning, and analysis components for time-series market data.

All providers return a canonical pandas `DataFrame` with a UTC `DatetimeIndex`
and the columns:

```text
open, high, low, close, volume, source
```

Dataset-level metadata such as `symbol` and `interval` is stored in
`DataFrame.attrs`. The `source` remains a column so observations from multiple
providers can be concatenated while retaining provenance.

## Data timing semantics

The two connectors provide observations with different timing semantics:

- **yfinance provides historical end-of-day data** when used with the default
  daily interval. Each row represents an OHLCV observation for a trading day.
- **Finnhub provides the current/latest time point.** Its single-row result is a
  snapshot of the current trading day: `open`, `high`, and `low` describe the
  day so far, while the current market price is normalized into the canonical
  `close` column.

This distinction matters when combining the providers. A yfinance daily row is
an end-of-day observation, whereas a Finnhub row obtained during market hours
represents an in-progress trading day and should not be interpreted as a final
daily close.

## Finnhub latest quotes

Set your API token in the environment:

```bash
export FINNHUB_API_KEY="your-token"
```

Then request the latest observation:

```python
from agentic_data_pipeline.ingestion import FinnhubClient

latest = FinnhubClient().get_latest("AAPL")
print(latest)
```

`get_quote()` remains available as a compatibility alias. Finnhub's current
price is normalized to the canonical `close` field. Quote responses do not
contain volume, so `volume` is `NaN`. Quote-only fields such as previous close
and percentage change are stored in `DataFrame.attrs`.

## Historical data with yfinance

The default daily history represents end-of-day observations:

```python
from agentic_data_pipeline.ingestion import YFinanceClient

history = YFinanceClient().get_history("AAPL", period="5y", interval="1d")
print(history.tail())
```

Because both providers return the same pandas representation, they can be
combined directly. Remember that `latest` may be an incomplete current-day
observation if the market is still open:

```python
import pandas as pd

history = YFinanceClient().get_history("AAPL", period="1y")
latest = FinnhubClient().get_latest("AAPL")
combined = pd.concat([history, latest]).sort_index()
```

## Stock time-series metrics

`add_stock_metrics()` appends commonly used features while keeping the result as
an ordinary pandas `DataFrame`. Pandas is used for returns and rolling
statistics, while the established `ta` package provides technical indicators.

```python
from agentic_data_pipeline import add_stock_metrics

features = add_stock_metrics(history)
```

The default feature set includes simple and log returns, cumulative return,
20/50-day simple moving averages, a 20-day EMA, rolling volatility, momentum,
RSI, MACD and signal/difference series, ATR, Bollinger Bands, drawdown, and
on-balance volume when complete volume data is available.

Series-level statistical diagnostics are available separately through
`time_series_diagnostics()`, which uses `statsmodels` on log returns:

```python
from agentic_data_pipeline import time_series_diagnostics

diagnostics = time_series_diagnostics(history, nlags=20)
```

The diagnostics include Augmented Dickey-Fuller and KPSS stationarity tests,
autocorrelation (ACF), and partial autocorrelation (PACF). These are returned as
summary statistics rather than appended as per-row columns.

## Benchmark-relative metrics

`HMWO.L` is the default benchmark symbol for benchmark-relative analysis.
Benchmark calculations accept a benchmark DataFrame explicitly so there are no
hidden network calls and callers can substitute another benchmark when needed.

```python
from agentic_data_pipeline import (
    DEFAULT_BENCHMARK,
    add_benchmark_metrics,
    benchmark_statistics,
)
from agentic_data_pipeline.ingestion import YFinanceClient

client = YFinanceClient()
asset = client.get_history("NVDA", period="5y")
benchmark = client.get_history(DEFAULT_BENCHMARK, period="5y")

summary = benchmark_statistics(asset, benchmark)
rolling = add_benchmark_metrics(asset, benchmark, window=90)
```

`benchmark_statistics()` returns beta, alpha, R-squared, correlation, annualised
excess return, tracking error, information ratio, upside/downside capture, and
asset/benchmark/relative maximum drawdowns. `add_benchmark_metrics()` appends
aligned benchmark return, excess return, rolling correlation, beta, alpha and
R-squared features.

See [`METRICS.md`](METRICS.md) for definitions, interpretation guidance and the
full list of metrics.

## Schema validation

The package exposes `create_market_data()` and `validate_market_data()` for
normalizing other providers into the same contract. Market data must have UTC
timestamps, OHLC values, non-negative volume where volume is present, a source,
and a symbol in `DataFrame.attrs`.

## Development

```bash
uv sync
uv run pytest
```

An executable NVIDIA/Finnhub walkthrough is available in
[`docs/finnhub_nvidia_examples.ipynb`](docs/finnhub_nvidia_examples.ipynb).
Install its optional dependencies with `uv sync --extra docs`.
