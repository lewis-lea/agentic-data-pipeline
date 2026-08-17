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

## Development

```bash
uv sync
uv run pytest
```

An executable NVIDIA/Finnhub walkthrough is available in
[`docs/finnhub_nvidia_examples.ipynb`](docs/finnhub_nvidia_examples.ipynb).
Install its optional dependencies with `uv sync --extra docs`.
