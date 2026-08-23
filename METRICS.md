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

Column: `return`

The percentage change in closing price from one observation to the next.

Use: measuring period-to-period performance and as a building block for benchmark-relative analysis.

### Log return

Column: `log_return`

The natural logarithm of the ratio between consecutive closes.

Use: statistical time-series modelling because log returns are additive over time and are generally more suitable than raw prices for stationarity-based methods.

### Cumulative return

Column: `cumulative_return`

The compounded return from the start of the supplied series.

Use: visualising total growth over the selected period.

### Simple moving averages

Columns: `sma_20`, `sma_50` by default.

Use: smoothing short-term price noise, identifying trend direction, and comparing short- and long-horizon trends.

### Exponential moving average

Column: `ema_20` by default.

Use: trend estimation with greater weighting on more recent observations.

## Volatility and momentum metrics

### Rolling volatility

Column: `volatility_20` by default.

The rolling standard deviation of log returns.

Use: measuring changing return dispersion and identifying volatility regimes.

### Momentum

Column: `momentum_20` by default.

The percentage price change over the selected lookback window.

Use: measuring medium-term trend strength.

### RSI

Column: `rsi_14` by default.

Relative Strength Index from the `ta` package.

Use: measuring recent upward versus downward price momentum. Traditionally interpreted on a 0-100 scale.

### MACD

Columns: `macd`, `macd_signal`, `macd_diff`.

Moving Average Convergence Divergence and its signal line.

Use: identifying changes in trend momentum and moving-average convergence/divergence.

### Average True Range

Column: `atr_14`.

Use: measuring typical trading range and price volatility using high, low and prior-close information.

### Bollinger Bands

Columns: `bollinger_mid`, `bollinger_high`, `bollinger_low`.

Use: comparing price with a moving mean and volatility-scaled upper/lower bands.

### On-Balance Volume

Column: `obv`.

Use: relating price direction to trading volume. The metric is returned as `NaN` when volume is incomplete, such as a Finnhub latest quote.

## Risk metrics

### Drawdown

Column: `drawdown`.

The percentage fall from the running peak close.

Use: quantifying loss from prior highs and identifying stress periods.

### Maximum drawdown

Returned by `benchmark_statistics()` as `max_drawdown`.

Use: summarising the worst peak-to-trough loss over the comparison period.

### Relative maximum drawdown

Returned as `relative_max_drawdown`.

Asset maximum drawdown minus benchmark maximum drawdown.

Use: identifying whether an asset suffered materially worse or better drawdowns than the benchmark.

## Statistical diagnostics

Function: `time_series_diagnostics()`.

Diagnostics are performed on log returns rather than raw prices.

### Augmented Dickey-Fuller test

Output: `adf`.

Use: testing the null hypothesis that the series contains a unit root and is non-stationary.

### KPSS test

Output: `kpss`.

Use: complementary stationarity test whose null hypothesis is stationarity.

### Autocorrelation function

Output: `acf`.

Use: measuring linear dependence between returns and their lagged values.

### Partial autocorrelation function

Output: `pacf`.

Use: measuring lag dependence after controlling for shorter lags, often useful when choosing autoregressive model order.

## Benchmark-relative statistics

Function: `benchmark_statistics(asset, benchmark)`.

The asset and benchmark are aligned on common timestamps and converted to close-to-close simple returns. `HMWO.L` is the repository's default benchmark symbol.

### Beta

Output: `beta`.

Estimated by OLS regression:

```text
asset_return = alpha + beta * benchmark_return + error
```

Use: measuring sensitivity to benchmark movements. Beta above 1 indicates greater benchmark sensitivity; below 1 indicates lower sensitivity.

### Alpha

Outputs: `alpha_per_period`, `alpha_annualized`.

The regression intercept from the same OLS model.

Use: estimating the component of average asset return not explained by benchmark exposure.

### R-squared

Output: `r_squared`.

Use: measuring the fraction of asset-return variation explained by the benchmark regression.

### Correlation

Output: `correlation`.

Use: measuring how closely asset and benchmark returns move together, independent of scale.

### Annualised excess return

Output: `excess_return_annualized`.

Mean asset return minus mean benchmark return, annualised using the configured periods per year.

Use: measuring straightforward active performance versus the benchmark.

### Tracking error

Output: `tracking_error_annualized`.

Annualised standard deviation of asset-minus-benchmark returns.

Use: measuring the volatility of active returns and how consistently the asset differs from the benchmark.

### Information ratio

Output: `information_ratio`.

Annualised mean active return divided by annualised tracking error.

Use: measuring excess return earned per unit of benchmark-relative risk.

### Upside capture

Output: `upside_capture`.

Mean asset return divided by mean benchmark return during periods when the benchmark return is positive.

Use: measuring how strongly the asset participates in rising markets. A value above 1 means the asset gained more than the benchmark on average during benchmark-up periods.

### Downside capture

Output: `downside_capture`.

Mean asset return divided by mean benchmark return during periods when the benchmark return is negative.

Use: measuring participation in falling markets. Values below 1 are generally preferable because the asset fell less than the benchmark on average.

## Rolling benchmark features

Function: `add_benchmark_metrics(asset, benchmark, window=90)`.

These features are useful for detecting changing regimes rather than relying on one full-period statistic.

### Benchmark return

Column: `benchmark_return`.

The benchmark close-to-close return aligned with the asset observation.

### Excess return

Column: `excess_return`.

Asset return minus benchmark return for each aligned period.

### Rolling correlation

Column: `rolling_correlation_<window>`.

Use: identifying changes in diversification and co-movement with the benchmark.

### Rolling beta

Column: `rolling_beta_<window>`.

Use: identifying changes in market sensitivity over time.

### Rolling alpha

Column: `rolling_alpha_<window>`.

Computed from rolling mean returns and rolling beta.

Use: identifying periods where benchmark-adjusted performance changes materially.

### Rolling R-squared

Column: `rolling_r_squared_<window>`.

For a one-factor benchmark relationship this is the square of rolling correlation.

Use: tracking how much of the asset's return behaviour is explained by the benchmark through time.

## Example

```python
from agentic_data_pipeline import (
    DEFAULT_BENCHMARK,
    add_benchmark_metrics,
    add_stock_metrics,
    benchmark_statistics,
    time_series_diagnostics,
)
from agentic_data_pipeline.ingestion import YFinanceClient

client = YFinanceClient()
asset = client.get_history("NVDA", period="5y")
benchmark = client.get_history(DEFAULT_BENCHMARK, period="5y")

features = add_stock_metrics(asset)
rolling = add_benchmark_metrics(asset, benchmark, window=90)
summary = benchmark_statistics(asset, benchmark)
diagnostics = time_series_diagnostics(asset)
```

## Interpretation caveats

These metrics describe historical behaviour; they do not imply future returns. Benchmark choice matters, and `HMWO.L` should be treated as a sensible default global-equity baseline rather than the correct benchmark for every security. Metrics based on daily returns also assume sufficiently overlapping trading dates and comparable pricing conventions between the asset and benchmark.
