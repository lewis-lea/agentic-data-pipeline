"""Tests for the canonical pandas market-data representation."""

import pandas as pd
import pytest

from agentic_data_pipeline import create_market_data, validate_market_data


def test_create_market_data_normalizes_columns_and_metadata() -> None:
    raw = pd.DataFrame(
        {
            "Open": [10.0],
            "High": [11.0],
            "Low": [9.0],
            "Close": [10.5],
            "Volume": [1000],
        },
        index=pd.DatetimeIndex(["2026-01-02"]),
    )

    frame = create_market_data(raw, symbol=" aapl ", source="test", interval="1d")

    assert frame.attrs == {"symbol": "AAPL", "interval": "1d"}
    assert list(frame.columns) == ["open", "high", "low", "close", "volume", "source"]
    assert str(frame.index.tz) == "UTC"
    assert frame.iloc[0]["source"] == "test"


def test_validate_market_data_rejects_invalid_high_low() -> None:
    raw = pd.DataFrame(
        {
            "open": [10.0],
            "high": [8.0],
            "low": [9.0],
            "close": [9.5],
            "volume": [1000],
            "source": ["test"],
        },
        index=pd.DatetimeIndex(["2026-01-02"], tz="UTC", name="timestamp"),
    )
    raw.attrs["symbol"] = "AAPL"

    with pytest.raises(ValueError, match="high must be greater"):
        validate_market_data(raw)


def test_market_data_from_multiple_sources_can_be_concatenated() -> None:
    history = create_market_data(
        pd.DataFrame(
            {"open": [10], "high": [11], "low": [9], "close": [10.5], "volume": [100]},
            index=pd.DatetimeIndex(["2026-01-02"]),
        ),
        symbol="AAPL",
        source="yfinance",
    )
    latest = create_market_data(
        pd.DataFrame(
            {"open": [10.5], "high": [12], "low": [10], "close": [11.5]},
            index=pd.DatetimeIndex(["2026-01-03"]),
        ),
        symbol="AAPL",
        source="finnhub",
    )

    combined = pd.concat([history, latest]).sort_index()

    assert combined["source"].tolist() == ["yfinance", "finnhub"]
    assert pd.isna(combined.iloc[1]["volume"])
