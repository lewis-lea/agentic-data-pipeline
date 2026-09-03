"""Tests for yfinance historical market-data ingestion."""

import pandas as pd
import pytest

from agentic_data_pipeline.ingestion import YFinanceClient, YFinanceError


def test_get_history_normalizes_dataframe() -> None:
    captured: dict[str, object] = {}

    def history_loader(symbol: str, **kwargs: object) -> pd.DataFrame:
        captured.update(symbol=symbol, **kwargs)
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1000, 1100],
            },
            index=pd.DatetimeIndex(["2026-01-02", "2026-01-05"], name="Date"),
        )

    frame = YFinanceClient(history_loader=history_loader).get_history(
        " aapl ", period="6mo", interval="1d"
    )

    assert isinstance(frame, pd.DataFrame)
    assert frame.attrs["symbol"] == "AAPL"
    assert frame.attrs["interval"] == "1d"
    assert list(frame.columns) == ["open", "high", "low", "close", "volume", "source"]
    assert len(frame) == 2
    assert frame.iloc[0]["source"] == "yfinance"
    assert frame.iloc[1]["close"] == 102.0
    assert str(frame.index.tz) == "UTC"
    assert captured == {
        "symbol": "AAPL",
        "interval": "1d",
        "auto_adjust": False,
        "actions": False,
        "period": "6mo",
    }


def test_get_history_prefers_explicit_date_range() -> None:
    captured: dict[str, object] = {}

    def history_loader(symbol: str, **kwargs: object) -> pd.DataFrame:
        captured.update(symbol=symbol, **kwargs)
        return pd.DataFrame(
            {"Open": [100.0], "High": [102.0], "Low": [99.0], "Close": [101.0], "Volume": [1000]},
            index=pd.DatetimeIndex(["2026-01-02"], name="Date"),
        )

    YFinanceClient(history_loader=history_loader).get_history(
        "AAPL", period="1y", start="2026-01-01", end="2026-02-01"
    )

    assert "period" not in captured
    assert captured["start"] == "2026-01-01"
    assert captured["end"] == "2026-02-01"


def test_get_history_rejects_empty_result() -> None:
    client = YFinanceClient(history_loader=lambda _symbol, **_kwargs: pd.DataFrame())

    with pytest.raises(YFinanceError, match="No historical data"):
        client.get_history("AAPL")


def test_get_history_rejects_empty_symbol() -> None:
    client = YFinanceClient(history_loader=lambda _symbol, **_kwargs: pd.DataFrame())

    with pytest.raises(ValueError, match="symbol must not be empty"):
        client.get_history("   ")
