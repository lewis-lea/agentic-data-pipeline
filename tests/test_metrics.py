"""Tests for stock time-series metrics and diagnostics."""

import numpy as np
import pandas as pd
import pytest

from agentic_data_pipeline import create_market_data
from agentic_data_pipeline.metrics import add_stock_metrics, time_series_diagnostics


def _market_frame(rows: int = 80) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=rows, freq="D", tz="UTC")
    trend = np.linspace(100.0, 130.0, rows)
    noise = np.sin(np.arange(rows) / 3.0)
    close = trend + noise
    raw = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.linspace(1000, 2000, rows),
        },
        index=index,
    )
    return create_market_data(raw, symbol="AAPL", source="test", interval="1d")


def test_add_stock_metrics_appends_expected_features_and_preserves_metadata() -> None:
    frame = _market_frame()

    enriched = add_stock_metrics(frame)

    expected = {
        "return",
        "log_return",
        "cumulative_return",
        "sma_20",
        "sma_50",
        "ema_20",
        "volatility_20",
        "momentum_20",
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_diff",
        "atr_14",
        "bollinger_mid",
        "bollinger_high",
        "bollinger_low",
        "drawdown",
        "obv",
    }
    assert expected.issubset(enriched.columns)
    assert enriched.attrs == frame.attrs
    assert enriched.index.equals(frame.index)
    assert enriched["cumulative_return"].iloc[0] == pytest.approx(0.0)
    assert enriched["drawdown"].max() <= 0.0
    assert enriched["obv"].notna().all()


def test_add_stock_metrics_uses_nan_obv_when_volume_is_incomplete() -> None:
    frame = _market_frame()
    frame.loc[frame.index[-1], "volume"] = np.nan

    enriched = add_stock_metrics(frame)

    assert enriched["obv"].isna().all()


def test_add_stock_metrics_rejects_invalid_windows() -> None:
    with pytest.raises(ValueError, match="short_window must be smaller"):
        add_stock_metrics(_market_frame(), short_window=50, long_window=20)


def test_time_series_diagnostics_returns_statsmodels_results() -> None:
    frame = _market_frame(120)

    diagnostics = time_series_diagnostics(frame, nlags=10)

    assert diagnostics["observations"] == 119
    assert set(diagnostics["adf"]) == {
        "statistic",
        "pvalue",
        "used_lag",
        "critical_values",
    }
    assert set(diagnostics["kpss"]) == {
        "statistic",
        "pvalue",
        "used_lag",
        "critical_values",
    }
    assert len(diagnostics["acf"]) == 11
    assert len(diagnostics["pacf"]) == 11


def test_time_series_diagnostics_rejects_short_history() -> None:
    with pytest.raises(ValueError, match="not enough observations"):
        time_series_diagnostics(_market_frame(8), nlags=5)
