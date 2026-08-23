"""Canonical pandas-based market-data schema and validation utilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
    """Normalize a DataFrame into the canonical market-data representation.

    The result uses a UTC ``DatetimeIndex`` and the columns ``open``, ``high``,
    ``low``, ``close``, ``volume`` and ``source``. Dataset-level metadata is
    stored in ``DataFrame.attrs``.
    """

    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")

    normalized_columns = {str(column).lower(): column for column in frame.columns}
    required_prices = {"open", "high", "low", "close"}
    missing = required_prices - normalized_columns.keys()
    if missing:
        raise ValueError(
            f"DataFrame is missing required columns: {', '.join(sorted(missing))}"
        )

    result = pd.DataFrame(index=pd.DatetimeIndex(pd.to_datetime(frame.index)))
    if result.index.tz is None:
        result.index = result.index.tz_localize("UTC")
    else:
        result.index = result.index.tz_convert("UTC")
    result.index.name = "timestamp"

    for column in ("open", "high", "low", "close"):
        result[column] = pd.to_numeric(frame[normalized_columns[column]], errors="raise").to_numpy()

    if "volume" in normalized_columns:
        result["volume"] = pd.to_numeric(
            frame[normalized_columns["volume"]], errors="coerce"
        ).to_numpy()
    else:
        result["volume"] = float("nan")

    if source is not None:
        result["source"] = source
    elif "source" in normalized_columns:
        result["source"] = frame[normalized_columns["source"]].astype(str).to_numpy()
    else:
        raise ValueError("source must be provided or present in the DataFrame")

    attrs = dict(metadata or {})
    attrs["symbol"] = normalized_symbol
    if interval is not None:
        attrs["interval"] = interval
    result.attrs = attrs

    return validate_market_data(result)


def validate_market_data(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and return a canonical market-data DataFrame."""

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    missing = set(MARKET_DATA_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(
            f"DataFrame is missing required columns: {', '.join(sorted(missing))}"
        )
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("market data must use a DatetimeIndex")
    if frame.index.tz is None or str(frame.index.tz) != "UTC":
        raise ValueError("market data index must use UTC")
    symbol = frame.attrs.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("market data attrs must contain a non-empty symbol")
    if (frame["high"] < frame["low"]).any():
        raise ValueError("high must be greater than or equal to low")
    non_null_volume = frame["volume"].dropna()
    if (non_null_volume < 0).any():
        raise ValueError("volume must not be negative")
    if frame["source"].isna().any() or (frame["source"].astype(str).str.strip() == "").any():
        raise ValueError("source must not be empty")
    return frame.sort_index()
