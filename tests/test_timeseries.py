"""Tests for canonical time-series models and pandas interoperability."""

from datetime import datetime, timezone

import pandas as pd

from agentic_data_pipeline import MarketQuote, TimeSeries, TimeSeriesPoint


def _point(day: int, close: float) -> TimeSeriesPoint:
    return TimeSeriesPoint(
        timestamp=datetime(2026, 1, day, tzinfo=timezone.utc),
        symbol="AAPL",
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        volume=1000,
        source="test",
    )


def test_timeseries_converts_to_dataframe_and_back() -> None:
    series = TimeSeries([_point(2, 102), _point(1, 101)])

    frame = series.to_dataframe()

    assert list(frame.index) == [
        pd.Timestamp("2026-01-01T00:00:00Z"),
        pd.Timestamp("2026-01-02T00:00:00Z"),
    ]
    assert frame.index.name == "timestamp"
    assert frame.loc[pd.Timestamp("2026-01-02T00:00:00Z"), "close"] == 102

    restored = TimeSeries.from_dataframe(frame)
    assert list(restored) == list(series)


def test_timeseries_from_yfinance_style_dataframe() -> None:
    frame = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [105.0],
            "Low": [99.0],
            "Close": [104.0],
            "Volume": [12345],
        },
        index=pd.DatetimeIndex(["2026-01-02"], name="Date"),
    )

    series = TimeSeries.from_dataframe(frame, symbol="aapl", source="yfinance")

    assert series.symbol == "AAPL"
    assert series[0].timestamp == datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert series[0].close == 104.0


def test_market_quote_converts_to_pandas() -> None:
    quote = MarketQuote(
        timestamp=datetime(2026, 1, 2, 12, tzinfo=timezone.utc),
        symbol="AAPL",
        current_price=104.0,
        open=100.0,
        high=105.0,
        low=99.0,
        previous_close=101.0,
        change=3.0,
        percent_change=2.97,
        source="finnhub",
    )

    pandas_series = quote.to_series()
    frame = quote.to_frame()

    assert pandas_series["current_price"] == 104.0
    assert pandas_series.name == pd.Timestamp("2026-01-02T12:00:00Z")
    assert frame.index.name == "timestamp"
    assert frame.iloc[0]["symbol"] == "AAPL"
