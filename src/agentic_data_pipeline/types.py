"""Canonical pandas-based market-data schema and validation utilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

MARKET_DATA_COLUMNS = ["open", "high", "low", "close", "volume", "source"]
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume"]


def create_market_data(
    frame: pd.DataFrame,
    *,
    symbol: str,
    source: str | None = None,
    interval: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Normalize a DataFrame into the canonical market-data representation."""
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")

    normalized_columns = {str(column).lower(): column for column in frame.columns}
    required_prices = {"open", "high", "low", "close"}
    missing = required_prices - normalized_columns.keys()
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {', '.join(sorted(missing))}")

    index = pd.DatetimeIndex(pd.to_datetime(frame.index))
    if index.tz is None:
        index = index.tz_localize("UTC")
    else:
        index = index.tz_convert("UTC")
    index.name = "timestamp"
    result = pd.DataFrame(index=index)

    for column in ("open", "high", "low", "close"):
        result[column] = pd.to_numeric(frame[normalized_columns[column]], errors="raise").to_numpy()
    result["volume"] = (
        pd.to_numeric(frame[normalized_columns["volume"]], errors="coerce").to_numpy()
        if "volume" in normalized_columns
        else float("nan")
    )
    if source is not None:
        result["source"] = source
    elif "source" in normalized_columns:
        result["source"] = frame[normalized_columns["source"]].astype(str).to_numpy()
    else:
        raise ValueError("source must be provided or present in the DataFrame")

    result.attrs.update(dict(metadata or {}))
    result.attrs["symbol"] = normalized_symbol
    if interval is not None:
        result.attrs["interval"] = interval
    return validate_market_data(result)


def validate_market_data(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and return a canonical market-data DataFrame."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    missing = set(MARKET_DATA_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {', '.join(sorted(missing))}")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("market data must use a DatetimeIndex")
    if frame.index.tz is None or str(frame.index.tz) != "UTC":
        raise ValueError("market data index must use UTC")
    if frame.index.hasnans:
        raise ValueError("market data timestamps must not be missing")
    if frame.index.has_duplicates:
        raise ValueError("market data timestamps must be unique")
    symbol = frame.attrs.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("market data attrs must contain a non-empty symbol")

    prices = frame[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    if prices.isna().any().any() or not np.isfinite(prices.to_numpy(dtype=float)).all():
        raise ValueError("OHLC values must be finite numbers")
    if (prices["high"] < prices[["open", "low", "close"]].max(axis=1)).any():
        raise ValueError("high must be greater than or equal to open, low and close")
    if (prices["low"] > prices[["open", "high", "close"]].min(axis=1)).any():
        raise ValueError("low must be less than or equal to open, high and close")

    volume = pd.to_numeric(frame["volume"], errors="coerce")
    non_null_volume = volume.dropna().to_numpy(dtype=float)
    if not np.isfinite(non_null_volume).all() or (non_null_volume < 0).any():
        raise ValueError("volume must be finite and non-negative when present")
    if frame["source"].isna().any() or (frame["source"].astype(str).str.strip() == "").any():
        raise ValueError("source must not be empty")
    return frame.sort_index()
