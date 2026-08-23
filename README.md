# Agentic Data Pipeline

Reusable ingestion and cleaning components for time-series data.

## Finnhub real-time quotes

Set your API token in the environment, then request a standardized quote:

```bash
export FINNHUB_API_KEY="your-token"
```

```python
from agentic_data_pipeline.ingestion import FinnhubClient

client = FinnhubClient()
quote = client.get_quote("AAPL")
print(quote.to_dict())
```

Each result is a provider-independent `MarketQuote` with a timezone-aware UTC
timestamp. The connector deliberately exposes only Finnhub's free real-time US
stock quote endpoint; premium historical candle APIs are not used.

`MarketQuote` integrates directly with pandas:

```python
quote_series = quote.to_series()
quote_frame = quote.to_frame()
```

## Historical data with yfinance

Historical OHLCV data can be fetched into a provider-independent `TimeSeries`:

```python
from agentic_data_pipeline.ingestion import YFinanceClient

client = YFinanceClient()
history = client.get_history("AAPL", period="5y", interval="1d")
```

Use explicit dates when preferred:

```python
history = client.get_history(
    "AAPL",
    start="2020-01-01",
    end="2026-01-01",
    interval="1d",
)
```

A `TimeSeries` is an ordered sequence of `TimeSeriesPoint` objects and converts
directly to a pandas `DataFrame`:

```python
frame = history.to_dataframe()
```

The reverse conversion is also supported for OHLCV DataFrames:

```python
from agentic_data_pipeline import TimeSeries

history = TimeSeries.from_dataframe(
    frame,
    symbol="AAPL",
    source="custom",
)
```

All canonical timestamps are timezone-aware UTC values. yfinance is an
open-source client for Yahoo Finance's publicly available interfaces; users
should ensure their use of downloaded data complies with the applicable Yahoo
terms.

## Development

```bash
uv sync
uv run pytest
```

An executable NVIDIA/Finnhub walkthrough is available in
[`docs/finnhub_nvidia_examples.ipynb`](docs/finnhub_nvidia_examples.ipynb).
Install its optional dependencies with `uv sync --extra docs`.
