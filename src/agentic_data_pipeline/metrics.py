"""Stock time-series metrics built on pandas, ta, and statsmodels."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import acf, adfuller, kpss, pacf
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD, SMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import OnBalanceVolumeIndicator

from agentic_data_pipeline.types import validate_market_data

DEFAULT_BENCHMARK = "HMWO.L"
TRADING_DAYS_PER_YEAR = 252


def add_stock_metrics(
    frame: pd.DataFrame,
    *,
    short_window: int = 20,
    long_window: int = 50,
    volatility_window: int = 20,
    momentum_window: int = 20,
    rsi_window: int = 14,
) -> pd.DataFrame:
    """Return market data with commonly used stock time-series metrics appended."""

    validate_market_data(frame)
    if min(short_window, long_window, volatility_window, momentum_window, rsi_window) <= 0:
        raise ValueError("metric windows must be positive")
    if short_window >= long_window:
        raise ValueError("short_window must be smaller than long_window")

    result = frame.copy()
    result.attrs = dict(frame.attrs)
    close = result["close"].astype(float)

    result["return"] = close.pct_change()
    result["log_return"] = np.log(close / close.shift(1))
    result["cumulative_return"] = (1.0 + result["return"].fillna(0.0)).cumprod() - 1.0

    result[f"sma_{short_window}"] = SMAIndicator(close, window=short_window).sma_indicator()
    result[f"sma_{long_window}"] = SMAIndicator(close, window=long_window).sma_indicator()
    result[f"ema_{short_window}"] = EMAIndicator(close, window=short_window).ema_indicator()

    result[f"volatility_{volatility_window}"] = result["log_return"].rolling(
        volatility_window
    ).std()
    result[f"momentum_{momentum_window}"] = close.pct_change(momentum_window)
    result[f"rsi_{rsi_window}"] = RSIIndicator(close, window=rsi_window).rsi()

    macd = MACD(close)
    result["macd"] = macd.macd()
    result["macd_signal"] = macd.macd_signal()
    result["macd_diff"] = macd.macd_diff()

    atr = AverageTrueRange(
        high=result["high"].astype(float),
        low=result["low"].astype(float),
        close=close,
        window=14,
    )
    result["atr_14"] = atr.average_true_range()

    bollinger = BollingerBands(close, window=20, window_dev=2)
    result["bollinger_mid"] = bollinger.bollinger_mavg()
    result["bollinger_high"] = bollinger.bollinger_hband()
    result["bollinger_low"] = bollinger.bollinger_lband()

    rolling_peak = close.cummax()
    result["drawdown"] = close / rolling_peak - 1.0

    if result["volume"].notna().all():
        result["obv"] = OnBalanceVolumeIndicator(
            close=close,
            volume=result["volume"].astype(float),
        ).on_balance_volume()
    else:
        result["obv"] = np.nan

    return result


def time_series_diagnostics(
    frame: pd.DataFrame,
    *,
    nlags: int = 20,
) -> dict[str, Any]:
    """Compute traditional statsmodels diagnostics on log returns."""

    validate_market_data(frame)
    if nlags <= 0:
        raise ValueError("nlags must be positive")

    close = frame["close"].astype(float)
    returns = np.log(close / close.shift(1)).dropna()
    if len(returns) < max(10, nlags + 2):
        raise ValueError("not enough observations for time-series diagnostics")

    effective_lags = min(nlags, len(returns) // 2 - 1)
    adf_result = adfuller(returns, autolag="AIC")
    kpss_result = kpss(returns, regression="c", nlags="auto")

    return {
        "observations": int(len(returns)),
        "adf": {
            "statistic": float(adf_result[0]),
            "pvalue": float(adf_result[1]),
            "used_lag": int(adf_result[2]),
            "critical_values": {key: float(value) for key, value in adf_result[4].items()},
        },
        "kpss": {
            "statistic": float(kpss_result[0]),
            "pvalue": float(kpss_result[1]),
            "used_lag": int(kpss_result[2]),
            "critical_values": {key: float(value) for key, value in kpss_result[3].items()},
        },
        "acf": acf(returns, nlags=effective_lags, fft=True).tolist(),
        "pacf": pacf(returns, nlags=effective_lags, method="ywm").tolist(),
    }


def benchmark_statistics(
    asset: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> dict[str, float | int | str]:
    """Return headline statistics for an asset relative to a benchmark.

    The two series are aligned on common timestamps and compared using simple
    close-to-close returns. Alpha and beta come from an OLS regression of asset
    returns on benchmark returns. Annualized values assume ``periods_per_year``
    observations per year (252 for daily trading data by default).
    """

    aligned = _aligned_returns(asset, benchmark)
    if len(aligned) < 3:
        raise ValueError("not enough overlapping observations for benchmark statistics")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")

    model = sm.OLS(aligned["asset_return"], sm.add_constant(aligned["benchmark_return"])).fit()
    alpha_period = float(model.params["const"])
    beta = float(model.params["benchmark_return"])
    active = aligned["asset_return"] - aligned["benchmark_return"]
    tracking_error_period = float(active.std(ddof=1))
    mean_active = float(active.mean())

    benchmark_up = aligned["benchmark_return"] > 0
    benchmark_down = aligned["benchmark_return"] < 0
    upside_capture = _capture_ratio(aligned, benchmark_up)
    downside_capture = _capture_ratio(aligned, benchmark_down)

    asset_cumulative = (1.0 + aligned["asset_return"]).cumprod()
    benchmark_cumulative = (1.0 + aligned["benchmark_return"]).cumprod()
    asset_drawdown = asset_cumulative / asset_cumulative.cummax() - 1.0
    benchmark_drawdown = benchmark_cumulative / benchmark_cumulative.cummax() - 1.0

    information_ratio = (
        mean_active / tracking_error_period * np.sqrt(periods_per_year)
        if tracking_error_period > 0
        else float("nan")
    )

    return {
        "benchmark": str(benchmark.attrs.get("symbol", DEFAULT_BENCHMARK)),
        "observations": int(len(aligned)),
        "beta": beta,
        "alpha_per_period": alpha_period,
        "alpha_annualized": float((1.0 + alpha_period) ** periods_per_year - 1.0),
        "r_squared": float(model.rsquared),
        "correlation": float(aligned["asset_return"].corr(aligned["benchmark_return"])),
        "excess_return_annualized": float(mean_active * periods_per_year),
        "tracking_error_annualized": float(tracking_error_period * np.sqrt(periods_per_year)),
        "information_ratio": float(information_ratio),
        "upside_capture": float(upside_capture),
        "downside_capture": float(downside_capture),
        "max_drawdown": float(asset_drawdown.min()),
        "benchmark_max_drawdown": float(benchmark_drawdown.min()),
        "relative_max_drawdown": float(asset_drawdown.min() - benchmark_drawdown.min()),
    }


def add_benchmark_metrics(
    asset: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    window: int = 90,
) -> pd.DataFrame:
    """Append rolling benchmark-relative features to an asset DataFrame.

    Adds benchmark return, excess return, rolling correlation, rolling beta,
    rolling alpha and rolling R-squared. Output is restricted to timestamps
    shared by both input series and preserves the asset metadata.
    """

    if window < 2:
        raise ValueError("window must be at least 2")
    aligned = _aligned_returns(asset, benchmark, include_close=True)
    result = asset.loc[aligned.index].copy()
    result.attrs = dict(asset.attrs)
    result.attrs["benchmark"] = str(benchmark.attrs.get("symbol", DEFAULT_BENCHMARK))

    asset_returns = aligned["asset_return"]
    benchmark_returns = aligned["benchmark_return"]
    result["benchmark_return"] = benchmark_returns
    result["excess_return"] = asset_returns - benchmark_returns
    result[f"rolling_correlation_{window}"] = asset_returns.rolling(window).corr(benchmark_returns)

    covariance = asset_returns.rolling(window).cov(benchmark_returns)
    benchmark_variance = benchmark_returns.rolling(window).var()
    rolling_beta = covariance / benchmark_variance
    result[f"rolling_beta_{window}"] = rolling_beta
    result[f"rolling_alpha_{window}"] = (
        asset_returns.rolling(window).mean()
        - rolling_beta * benchmark_returns.rolling(window).mean()
    )
    result[f"rolling_r_squared_{window}"] = result[f"rolling_correlation_{window}"] ** 2
    return result


def _aligned_returns(
    asset: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    include_close: bool = False,
) -> pd.DataFrame:
    validate_market_data(asset)
    validate_market_data(benchmark)

    columns: dict[str, pd.Series] = {
        "asset_return": asset["close"].astype(float).pct_change(),
        "benchmark_return": benchmark["close"].astype(float).pct_change(),
    }
    if include_close:
        columns["asset_close"] = asset["close"].astype(float)
        columns["benchmark_close"] = benchmark["close"].astype(float)
    return pd.concat(columns, axis=1, join="inner").dropna(subset=["asset_return", "benchmark_return"])


def _capture_ratio(aligned: pd.DataFrame, mask: pd.Series) -> float:
    subset = aligned.loc[mask]
    if subset.empty:
        return float("nan")
    benchmark_mean = float(subset["benchmark_return"].mean())
    if benchmark_mean == 0:
        return float("nan")
    return float(subset["asset_return"].mean() / benchmark_mean)
