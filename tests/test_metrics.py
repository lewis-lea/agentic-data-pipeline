"""Tests for stock time-series metrics and diagnostics."""

import numpy as np
import pandas as pd
import pytest

from agentic_data_pipeline import create_market_data
from agentic_data_pipeline.metrics import (
    add_benchmark_metrics,
    add_stock_metrics,
    benchmark_statistics,
    time_series_diagnostics,
)


def _market_frame(rows: int = 80, *, symbol: str = "AAPL", scale: float = 1.0) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=rows, freq="D", tz="UTC")
    trend = np.linspace(100.0, 130.0, rows)
    noise = np.sin(np.arange(rows) / 3.0)
    close = (trend + noise) * scale
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
    return create_market_data(raw, symbol=symbol, source="test", interval="1d")


def _frame_from_returns(returns: np.ndarray, *, symbol: str) -> pd.DataFrame:
    close = 100.0 * np.cumprod(np.r_[1.0, 1.0 + returns])
    index = pd.date_range("2026-01-01", periods=len(close), freq="D", tz="UTC")
    raw = pd.DataFrame(
        {
            "open": close,
            "high": close * 1.001,
            "low": close * 0.999,
            "close": close,
            "volume": 1000.0,
        },
        index=index,
    )
    return create_market_data(raw, symbol=symbol, source="test", interval="1d")


def test_add_stock_metrics_appends_expected_features_and_preserves_metadata() -> None:
    frame = _market_frame()
    enriched = add_stock_metrics(frame)
    expected = {
        "return", "log_return", "cumulative_return", "sma_20", "sma_50", "ema_20",
        "volatility_20", "momentum_20", "rsi_14", "macd", "macd_signal", "macd_diff",
        "atr_14", "bollinger_mid", "bollinger_high", "bollinger_low", "drawdown", "obv",
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
    diagnostics = time_series_diagnostics(_market_frame(120), nlags=10)
    assert diagnostics["observations"] == 119
    assert set(diagnostics["adf"]) == {"statistic", "pvalue", "used_lag", "critical_values"}
    assert set(diagnostics["kpss"]) == {"statistic", "pvalue", "used_lag", "critical_values"}
    assert len(diagnostics["acf"]) == 11
    assert len(diagnostics["pacf"]) == 11


def test_time_series_diagnostics_rejects_short_history() -> None:
    with pytest.raises(ValueError, match="not enough observations"):
        time_series_diagnostics(_market_frame(8), nlags=5)


def test_benchmark_statistics_recovers_known_alpha_beta_relationship() -> None:
    benchmark_returns = np.array([0.01, -0.005, 0.002, 0.008, -0.004, 0.006, 0.003, -0.002])
    asset_returns = 0.001 + 1.5 * benchmark_returns
    benchmark = _frame_from_returns(benchmark_returns, symbol="HMWO.L")
    asset = _frame_from_returns(asset_returns, symbol="TEST")

    stats = benchmark_statistics(asset, benchmark, periods_per_year=252)

    assert stats["benchmark"] == "HMWO.L"
    assert stats["beta"] == pytest.approx(1.5, rel=1e-10)
    assert stats["alpha_per_period"] == pytest.approx(0.001, rel=1e-10)
    assert stats["r_squared"] == pytest.approx(1.0)
    assert stats["correlation"] == pytest.approx(1.0)


def test_add_benchmark_metrics_adds_rolling_features_and_metadata() -> None:
    benchmark_returns = np.linspace(-0.01, 0.01, 20)
    asset_returns = 0.0005 + 1.2 * benchmark_returns
    benchmark = _frame_from_returns(benchmark_returns, symbol="HMWO.L")
    asset = _frame_from_returns(asset_returns, symbol="TEST")

    enriched = add_benchmark_metrics(asset, benchmark, window=5)

    assert enriched.attrs["benchmark"] == "HMWO.L"
    assert "benchmark_return" in enriched
    assert "excess_return" in enriched
    assert "rolling_beta_5" in enriched
    assert "rolling_alpha_5" in enriched
    assert "rolling_correlation_5" in enriched
    assert "rolling_r_squared_5" in enriched
    assert enriched["rolling_beta_5"].dropna().iloc[-1] == pytest.approx(1.2, rel=1e-10)
