"""Stock time-series metrics built on pandas, ta, and statsmodels."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import acf, adfuller, kpss, pacf
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD, SMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import OnBalanceVolumeIndicator

from agentic_data_pipeline.types import validate_market_data


def add_stock_metrics(
    frame: pd.DataFrame,
    *,
    short_window: int = 20,
    long_window: int = 50,
    volatility_window: int = 20,
    momentum_window: int = 20,
    rsi_window: int = 14,
) -> pd.DataFrame:
    """Return market data with commonly used stock time-series metrics appended.

    The input must satisfy the repository's canonical market-data schema. The
    returned frame preserves the original metadata in ``DataFrame.attrs``.
    Metrics are computed from the ``close`` series unless an OHLCV indicator
    naturally requires other columns.
    """

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
    """Compute traditional statsmodels diagnostics on log returns.

    Returns ADF and KPSS stationarity tests plus autocorrelation and partial
    autocorrelation arrays. Missing values from the initial return calculation
    are removed before diagnostics are evaluated.
    """

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
