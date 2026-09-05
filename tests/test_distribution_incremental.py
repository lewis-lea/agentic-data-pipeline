"""Tests for persisted yfinance distribution history."""

from __future__ import annotations

import pandas as pd
import pytest

from agentic_data_pipeline.incremental import update_yfinance_distributions
from agentic_data_pipeline.storage import ParquetStorage


class FakeDistributionClient:
    def __init__(self, responses: list[pd.DataFrame]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def get_distributions(
        self,
        symbol: str,
        *,
        start: object = None,
        end: object = None,
    ) -> pd.DataFrame:
        self.calls.append({"symbol": symbol, "start": start, "end": end})
        return self.responses.pop(0).copy()


def distribution_frame(
    dates: list[str],
    amounts: list[float],
    *,
    symbol: str = "ABC",
) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "cash_amount": amounts,
            "source": ["yfinance"] * len(amounts),
        },
        index=pd.DatetimeIndex(dates, tz="UTC", name="timestamp"),
    )
    frame.attrs = {
        "symbol": symbol,
        "dataset": "distributions",
        "source": "yfinance",
    }
    return frame


def test_first_distribution_update_persists_full_history(tmp_path) -> None:
    client = FakeDistributionClient(
        [distribution_frame(["2026-01-15", "2026-04-15"], [0.2, 0.25])]
    )
    storage = ParquetStorage(tmp_path)

    result = update_yfinance_distributions(
        " abc ",
        end="2026-06-01",
        storage=storage,
        client=client,  # type: ignore[arg-type]
    )

    assert result["cash_amount"].tolist() == [0.2, 0.25]
    assert client.calls == [
        {"symbol": "ABC", "start": None, "end": "2026-06-01"}
    ]
    assert storage.dataset_path(
        source="yfinance",
        dataset="distributions",
        symbol="ABC",
    ).exists()


def test_incremental_distribution_update_refetches_boundary_and_replaces_it(tmp_path) -> None:
    storage = ParquetStorage(tmp_path)
    first = distribution_frame(["2026-01-15", "2026-04-15"], [0.2, 0.25])
    storage.save_dataset(
        first,
        source="yfinance",
        dataset="distributions",
        symbol="ABC",
    )

    client = FakeDistributionClient(
        [distribution_frame(["2026-04-15", "2026-07-15"], [0.3, 0.35])]
    )
    result = update_yfinance_distributions(
        "ABC",
        storage=storage,
        client=client,  # type: ignore[arg-type]
    )

    assert result["cash_amount"].tolist() == [0.2, 0.3, 0.35]
    assert client.calls[0]["start"] == pd.Timestamp("2026-04-15", tz="UTC")


def test_distribution_update_returns_existing_when_end_is_already_covered(tmp_path) -> None:
    storage = ParquetStorage(tmp_path)
    storage.save_dataset(
        distribution_frame(["2026-04-15"], [0.25]),
        source="yfinance",
        dataset="distributions",
        symbol="ABC",
    )
    client = FakeDistributionClient([])

    result = update_yfinance_distributions(
        "ABC",
        end="2026-04-15",
        storage=storage,
        client=client,  # type: ignore[arg-type]
    )

    assert result["cash_amount"].tolist() == [0.25]
    assert client.calls == []


def test_empty_persisted_distribution_dataset_is_checked_again(tmp_path) -> None:
    storage = ParquetStorage(tmp_path)
    empty = distribution_frame([], [])
    storage.save_dataset(
        empty,
        source="yfinance",
        dataset="distributions",
        symbol="ABC",
    )
    client = FakeDistributionClient([distribution_frame([], [])])

    result = update_yfinance_distributions(
        "ABC",
        storage=storage,
        client=client,  # type: ignore[arg-type]
    )

    assert result.empty
    assert client.calls == [{"symbol": "ABC", "start": None, "end": None}]


def test_distribution_update_rejects_empty_symbol() -> None:
    with pytest.raises(ValueError, match="symbol"):
        update_yfinance_distributions(" ")
