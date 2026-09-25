"""Tests for DuckDB bitemporal persistence."""

from datetime import UTC, datetime

import pandas as pd

from agentic_data_pipeline.storage import DuckDBStorage
from agentic_data_pipeline.types import create_market_data


def _frame(close: float) -> pd.DataFrame:
    raw = pd.DataFrame(
        {"open": [100.0], "high": [105.0], "low": [99.0], "close": [close], "volume": [1000.0]},
        index=pd.DatetimeIndex(["2026-01-02T00:00:00Z"]),
    )
    return create_market_data(raw, symbol="NVDA", source="yfinance", interval="1d")


def test_duckdb_retains_versions_and_loads_latest(tmp_path) -> None:
    storage = DuckDBStorage(tmp_path / "market.duckdb")
    first = datetime(2026, 1, 3, tzinfo=UTC)
    second = datetime(2026, 1, 4, tzinfo=UTC)
    storage.save_market_data(_frame(101.0), source="yfinance", interval="1d", available_timestamp=first)
    storage.save_market_data(_frame(102.0), source="yfinance", interval="1d", update=True, available_timestamp=second)
    latest = storage.load_market_data(source="yfinance", interval="1d", symbol="NVDA")
    history = storage.load_market_data(source="yfinance", interval="1d", symbol="NVDA", history=True)
    assert latest.iloc[0]["close"] == 102.0
    assert len(history) == 2
    assert "available_timestamp" in history.columns


def test_duckdb_as_of_prevents_future_knowledge(tmp_path) -> None:
    storage = DuckDBStorage(tmp_path / "market.duckdb")
    storage.save_market_data(_frame(101.0), source="yfinance", interval="1d",
                             available_timestamp=datetime(2026, 1, 3, tzinfo=UTC))
    storage.save_market_data(_frame(104.0), source="yfinance", interval="1d", update=True,
                             available_timestamp=datetime(2026, 1, 5, tzinfo=UTC))
    known = storage.load_market_data(source="yfinance", interval="1d", symbol="NVDA",
                                     as_of=datetime(2026, 1, 4, tzinfo=UTC))
    assert known.iloc[0]["close"] == 101.0
