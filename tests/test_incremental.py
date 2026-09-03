"""Tests for incremental persisted ingestion workflows."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from agentic_data_pipeline.incremental import update_yfinance_market_data
from agentic_data_pipeline.storage import ParquetStorage
from agentic_data_pipeline.types import create_market_data


def _market_frame(symbol: str, dates: list[str], closes: list[float]) -> pd.DataFrame:
    raw = pd.DataFrame(
        {
            "open": closes,
            "high": [value + 1 for value in closes],
            "low": [value - 1 for value in closes],
            "close": closes,
            "volume": [1000 + index for index in range(len(closes))],
        },
        index=pd.DatetimeIndex(dates),
    )
    return create_market_data(
        raw,
        symbol=symbol,
        source="yfinance",
        interval="1d",
    )


class FakeYFinanceClient:
    def __init__(self, responses: list[pd.DataFrame]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def get_history(self, symbol: str, **kwargs: object) -> pd.DataFrame:
        self.calls.append({"symbol": symbol, **kwargs})
        return self.responses.pop(0)


def test_first_run_fetches_initial_period_and_persists(tmp_path: Path) -> None:
    storage = ParquetStorage(tmp_path)
    client = FakeYFinanceClient(
        [_market_frame("NVDA", ["2026-01-02", "2026-01-05"], [100.0, 101.0])]
    )

    result = update_yfinance_market_data(
        " nvda ",
        initial_period="2y",
        storage=storage,
        client=client,
    )

    assert len(result) == 2
    assert client.calls == [
        {
            "symbol": "NVDA",
            "period": "2y",
            "interval": "1d",
            "end": None,
            "auto_adjust": False,
        }
    ]
    assert storage.market_data_path(
        source="yfinance", interval="1d", symbol="NVDA"
    ).exists()


def test_update_starts_at_latest_persisted_timestamp_and_new_bar_wins(tmp_path: Path) -> None:
    storage = ParquetStorage(tmp_path)
    initial = _market_frame(
        "NVDA",
        ["2026-01-02", "2026-01-05"],
        [100.0, 101.0],
    )
    storage.save_market_data(initial, source="yfinance", interval="1d")

    refresh = _market_frame(
        "NVDA",
        ["2026-01-05", "2026-01-06"],
        [101.5, 103.0],
    )
    client = FakeYFinanceClient([refresh])

    result = update_yfinance_market_data(
        "NVDA",
        storage=storage,
        client=client,
    )

    assert len(result) == 3
    assert result.loc[pd.Timestamp("2026-01-05", tz="UTC"), "close"] == 101.5
    assert result.loc[pd.Timestamp("2026-01-06", tz="UTC"), "close"] == 103.0
    assert client.calls[0]["period"] is None
    assert client.calls[0]["start"] == pd.Timestamp("2026-01-05", tz="UTC")


def test_explicit_end_at_or_before_latest_timestamp_is_noop(tmp_path: Path) -> None:
    storage = ParquetStorage(tmp_path)
    initial = _market_frame(
        "NVDA",
        ["2026-01-02", "2026-01-05"],
        [100.0, 101.0],
    )
    storage.save_market_data(initial, source="yfinance", interval="1d")
    client = FakeYFinanceClient([])

    result = update_yfinance_market_data(
        "NVDA",
        end="2026-01-05",
        storage=storage,
        client=client,
    )

    assert len(result) == 2
    assert client.calls == []


def test_incremental_ingestion_respects_interval_partition(tmp_path: Path) -> None:
    storage = ParquetStorage(tmp_path)
    frame = _market_frame("AAPL", ["2026-01-02"], [200.0])
    frame.attrs["interval"] = "1h"
    client = FakeYFinanceClient([frame])

    update_yfinance_market_data(
        "AAPL",
        interval="1h",
        storage=storage,
        client=client,
    )

    assert storage.market_data_path(
        source="yfinance", interval="1h", symbol="AAPL"
    ).exists()
