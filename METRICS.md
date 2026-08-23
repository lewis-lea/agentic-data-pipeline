# Stock Time-Series Metrics

This document describes the metrics exposed by `agentic_data_pipeline.metrics`, what they measure, and how they are intended to be used.

The package uses `HMWO.L` (HSBC MSCI World UCITS ETF, London listing) as the default benchmark symbol for benchmark-relative analysis. Benchmark functions still accept any compatible market-data DataFrame so callers can substitute a more appropriate benchmark where needed.

## Input assumptions

Metric functions operate on the repository's canonical pandas market-data schema:

```text
DatetimeIndex (UTC)
open, high, low, close, volume, source
```

The asset symbol is stored in `DataFrame.attrs["symbol"]`. Daily benchmark statistics assume 252 trading periods per year unless overridden.

## Returns and trend metrics

### Simple return

Column: `return`. Percentage change in closing price from one observation to the next. Use: period-to-period performance and benchmark-relative analysis.

### Log return

Column: `log_return`. Natural logarithm of the ratio between consecutive closes. Use: statistical time-series modelling and additive multi-period returns.

### Cumulative return

Column: `cumulative_return`. Compounded return from the start of the series. Use: total growth over the selected period.

### Moving averages

Columns: `sma_20`, `sma_50`, `ema_20` by default. Use: smoothing price noise and identifying trend direction.

## Volatility and momentum metrics

### Rolling volatility

Column: `volatility_20` by default. Rolling standard deviation of log returns. Use: changing return dispersion and volatility regimes.

### Momentum

Column: `momentum_20` by default. Percentage price change over the lookback window. Use: medium-term trend strength.

### RSI

Column: `rsi_14`. Relative Strength Index from `ta`. Use: recent upward versus downward price momentum.

### MACD

Columns: `macd`, `macd_signal`, `macd_diff`. Use: changes in trend momentum.

### Average True Range

Column: `atr_14`. Use: typical trading range and price volatility.

### Bollinger Bands

Columns: `bollinger_mid`, `bollinger_high`, `bollinger_low`. Use: comparing price with a moving mean and volatility-scaled bands.

### On-Balance Volume

Column: `obv`. Use: relating price direction to trading volume. Returned as `NaN` when volume is incomplete.

## Risk metrics

### Drawdown

Column: `drawdown`. Percentage fall from the running peak close. Use: quantifying losses from prior highs.

### Maximum and relative maximum drawdown

`benchmark_statistics()` returns `max_drawdown`, `benchmark_max_drawdown`, and `relative_max_drawdown`. Use: comparing peak-to-trough losses with the benchmark.

## Statistical diagnostics

Function: `time_series_diagnostics()`. Diagnostics are performed on log returns.

- **ADF**: tests the null hypothesis that the series contains a unit root.
- **KPSS**: complementary test whose null hypothesis is stationarity.
- **ACF**: linear dependence between returns and lagged values.
- **PACF**: lag dependence after controlling for shorter lags.

## Benchmark-relative statistics

Function: `benchmark_statistics(asset, benchmark)`. Asset and benchmark are aligned on common timestamps and converted to close-to-close returns.

- **Beta**: OLS sensitivity of asset returns to benchmark returns.
- **Alpha**: regression intercept, returned per-period and annualised.
- **R-squared**: fraction of asset-return variation explained by the benchmark.
- **Correlation**: return co-movement independent of scale.
- **Annualised excess return**: mean asset minus benchmark return, annualised.
- **Tracking error**: annualised standard deviation of active returns.
- **Information ratio**: excess return per unit of tracking error.
- **Upside capture**: relative performance during benchmark-up periods.
- **Downside capture**: relative performance during benchmark-down periods.

## Rolling benchmark features

Function: `add_benchmark_metrics(asset, benchmark, window=90)`.

Columns include `benchmark_return`, `excess_return`, `rolling_correlation_<window>`, `rolling_beta_<window>`, `rolling_alpha_<window>`, and `rolling_r_squared_<window>`. Use: detecting changes in market sensitivity, diversification and benchmark-adjusted performance through time.

## Qualitative Finnhub signals

These are provider observations rather than price-derived statistics. They are returned as pandas DataFrames by `FinnhubClient` and can be aligned with market data for feature engineering.

### Analyst recommendation trends

Function: `FinnhubClient.get_recommendation_trends(symbol)`.

Finnhub supplies monthly counts in five recommendation categories: strong buy, buy, hold, sell and strong sell. The connector also derives:

- `analyst_count`: total recommendations in the observation.
- `analyst_sentiment`: normalized consensus score from -1 to +1, calculated as `(2*strong_buy + buy - sell - 2*strong_sell) / (2*analyst_count)`.

Use: measuring professional analyst consensus and changes in consensus over time. A value near +1 indicates strongly bullish consensus, zero is approximately neutral, and -1 indicates strongly bearish consensus.

### Insider sentiment

Function: `FinnhubClient.get_insider_sentiment(symbol, start=..., end=...)`.

Columns:

- `mspr`: Finnhub's monthly insider sentiment score.
- `change`: aggregate insider share change reported by the endpoint.

Use: capturing a qualitatively different signal from analyst opinion: the behaviour of corporate insiders. Changes in MSPR can be investigated alongside price, momentum and analyst-consensus changes.

Both qualitative datasets use a UTC monthly `DatetimeIndex`, store the ticker in `DataFrame.attrs["symbol"]`, and retain `source="finnhub"` as a column. They should not be interpreted as daily observations; when joining them to daily price data, the alignment/forward-fill policy should be explicit to avoid look-ahead bias.

## Example

```python
from agentic_data_pipeline import (
    DEFAULT_BENCHMARK,
    add_benchmark_metrics,
    add_stock_metrics,
    benchmark_statistics,
    time_series_diagnostics,
)
from agentic_data_pipeline.ingestion import FinnhubClient, YFinanceClient

prices = YFinanceClient()
asset = prices.get_history("NVDA", period="5y")
benchmark = prices.get_history(DEFAULT_BENCHMARK, period="5y")

features = add_stock_metrics(asset)
rolling = add_benchmark_metrics(asset, benchmark, window=90)
summary = benchmark_statistics(asset, benchmark)
diagnostics = time_series_diagnostics(asset)

finnhub = FinnhubClient()
recommendations = finnhub.get_recommendation_trends("NVDA")
insider = finnhub.get_insider_sentiment("NVDA")
```

## Interpretation caveats

These metrics and signals describe historical observations; they do not imply future returns. Benchmark choice matters, and `HMWO.L` is a default global-equity baseline rather than the correct benchmark for every security. Qualitative observations may be revised, sparse, delayed or subject to provider-plan availability. Feature pipelines must preserve the date on which information became available to avoid look-ahead bias.
