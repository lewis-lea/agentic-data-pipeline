import json

import pandas as pd
import pandas.testing as pdt

from agentic_data_pipeline.storage import ParquetStorage
from agentic_data_pipeline.types import create_market_data


def _market_frame(symbol: str = "NVDA") -> pd.DataFrame:
    index = pd.DatetimeIndex(
        ["2026-08-31T00:00:00Z", "2026-09-01T00:00:00Z"],
        name="timestamp",
    )
    raw = pd.DataFrame(
        {
            "open": [100.0, 102.0],
            "high": [103.0, 105.0],
            "low": [99.0, 101.0],
            "close": [102.0, 104.0],
            "volume": [1_000.0, 1_100.0],
        },
        index=index,
    )
    return create_market_data(
        raw,
        symbol=symbol,
        source="yfinance",
        interval="1d",
        metadata={"currency": "USD"},
    )


def test_market_data_round_trip_uses_interval_first_layout(tmp_path):
    storage = ParquetStorage(tmp_path)
    frame = _market_frame()

    path = storage.save_market_data(frame, source="yfinance", interval="1d")
    loaded = storage.load_market_data(
        source="yfinance", interval="1d", symbol="NVDA"
    )

    assert path == tmp_path / "raw" / "yfinance" / "1d" / "NVDA.parquet"
    pdt.assert_frame_equal(loaded, frame)
    assert loaded.attrs == {"currency": "USD", "symbol": "NVDA", "interval": "1d"}

    metadata = json.loads(path.with_suffix(".metadata.json").read_text())
    assert metadata["schema_version"] == 1
    assert metadata["rows"] == 2
    assert metadata["symbol"] == "NVDA"
    assert metadata["interval"] == "1d"


def test_market_data_update_replaces_duplicate_timestamp(tmp_path):
    storage = ParquetStorage(tmp_path)
    original = _market_frame().iloc[[0]].copy()
    original.attrs = dict(_market_frame().attrs)
    storage.save_market_data(original, source="yfinance", interval="1d")

    replacement = _market_frame().iloc[[0]].copy()
    replacement.loc[:, "close"] = 101.5
    replacement.attrs = dict(_market_frame().attrs)
    storage.save_market_data(
        replacement, source="yfinance", interval="1d", update=True
    )

    loaded = storage.load_market_data(
        source="yfinance", interval="1d", symbol="NVDA"
    )
    assert len(loaded) == 1
    assert loaded.iloc[0]["close"] == 101.5


def test_qualitative_dataset_round_trip(tmp_path):
    storage = ParquetStorage(tmp_path)
    frame = pd.DataFrame(
        {
            "strong_buy": [10, 11],
            "buy": [5, 6],
            "hold": [2, 2],
            "sell": [1, 1],
            "strong_sell": [0, 0],
            "analyst_count": [18, 20],
            "analyst_sentiment": [0.6389, 0.65],
            "source": ["finnhub", "finnhub"],
        },
        index=pd.DatetimeIndex(
            ["2026-08-01T00:00:00Z", "2026-09-01T00:00:00Z"],
            name="timestamp",
        ),
    )
    frame.attrs = {"symbol": "NVDA", "frequency": "monthly"}

    path = storage.save_dataset(
        frame, source="finnhub", dataset="recommendations"
    )
    loaded = storage.load_dataset(
        source="finnhub", dataset="recommendations", symbol="NVDA"
    )

    assert path == tmp_path / "raw" / "finnhub" / "recommendations" / "NVDA.parquet"
    pdt.assert_frame_equal(loaded, frame)
    assert loaded.attrs == frame.attrs


def test_qualitative_update_keeps_newest_duplicate(tmp_path):
    storage = ParquetStorage(tmp_path)
    index = pd.DatetimeIndex(["2026-08-01T00:00:00Z"], name="timestamp")
    original = pd.DataFrame({"mspr": [5.0], "change": [10.0]}, index=index)
    original.attrs = {"symbol": "NVDA", "frequency": "monthly"}
    storage.save_dataset(
        original, source="finnhub", dataset="insider_sentiment"
    )

    update = pd.DataFrame({"mspr": [7.0], "change": [12.0]}, index=index)
    update.attrs = dict(original.attrs)
    storage.save_dataset(
        update,
        source="finnhub",
        dataset="insider_sentiment",
        update=True,
    )

    loaded = storage.load_dataset(
        source="finnhub", dataset="insider_sentiment", symbol="NVDA"
    )
    assert loaded.iloc[0]["mspr"] == 7.0
