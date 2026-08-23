"""Provider-independent time-series domain models."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd


def _validate_utc_timestamp(timestamp: datetime) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    if timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
        raise ValueError("timestamp must use UTC")


@dataclass(frozen=True, slots=True)
class TimeSeriesPoint:
    """A standardized OHLCV observation from any market-data provider."""

    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str

    def __post_init__(self) -> None:
        _validate_utc_timestamp(self.timestamp)
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")
        if self.volume < 0:
            raise ValueError("volume must not be negative")

    def to_dict(self) -> dict[str, Any]:
        """Return a serialization-friendly representation of this point."""

        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat().replace("+00:00", "Z")
        return result

    def to_series(self) -> pd.Series:
        """Return the observation as a pandas Series named by its timestamp."""

        return pd.Series(
            {
                "symbol": self.symbol,
                "open": self.open,
                "high": self.high,
                "low": self.low,
                "close": self.close,
                "volume": self.volume,
                "source": self.source,
            },
            name=pd.Timestamp(self.timestamp),
        )

    def to_frame(self) -> pd.DataFrame:
        """Return a one-row pandas DataFrame indexed by timestamp."""

        frame = self.to_series().to_frame().T
        frame.index.name = "timestamp"
        return frame


@dataclass(frozen=True, slots=True)
class MarketQuote:
    """A standardized point-in-time market quote."""

    timestamp: datetime
    symbol: str
    current_price: float
    open: float
    high: float
    low: float
    previous_close: float
    change: float | None
    percent_change: float | None
    source: str

    def __post_init__(self) -> None:
        _validate_utc_timestamp(self.timestamp)
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")

    def to_dict(self) -> dict[str, Any]:
        """Return a serialization-friendly representation of this quote."""

        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat().replace("+00:00", "Z")
        return result

    def to_series(self) -> pd.Series:
        """Return the quote as a pandas Series named by its timestamp."""

        return pd.Series(
            {
                "symbol": self.symbol,
                "current_price": self.current_price,
                "open": self.open,
                "high": self.high,
                "low": self.low,
                "previous_close": self.previous_close,
                "change": self.change,
                "percent_change": self.percent_change,
                "source": self.source,
            },
            name=pd.Timestamp(self.timestamp),
        )

    def to_frame(self) -> pd.DataFrame:
        """Return a one-row pandas DataFrame indexed by timestamp."""

        frame = self.to_series().to_frame().T
        frame.index.name = "timestamp"
        return frame


class TimeSeries(Sequence[TimeSeriesPoint]):
    """Ordered provider-independent OHLCV history with pandas interoperability."""

    def __init__(self, points: Iterable[TimeSeriesPoint] = ()) -> None:
        self._points = tuple(sorted(points, key=lambda point: point.timestamp))
        symbols = {point.symbol for point in self._points}
        if len(symbols) > 1:
            raise ValueError("a TimeSeries must contain only one symbol")

    def __len__(self) -> int:
        return len(self._points)

    def __getitem__(self, index: int | slice) -> TimeSeriesPoint | TimeSeries:
        if isinstance(index, slice):
            return TimeSeries(self._points[index])
        return self._points[index]

    def __iter__(self) -> Iterator[TimeSeriesPoint]:
        return iter(self._points)

    @property
    def symbol(self) -> str | None:
        """Return the series symbol, or None for an empty series."""

        return self._points[0].symbol if self._points else None

    def to_dataframe(self) -> pd.DataFrame:
        """Return OHLCV observations as a UTC DatetimeIndex pandas DataFrame."""

        columns = ["symbol", "open", "high", "low", "close", "volume", "source"]
        if not self._points:
            frame = pd.DataFrame(columns=columns)
            frame.index = pd.DatetimeIndex([], tz="UTC", name="timestamp")
            return frame

        frame = pd.DataFrame(
            [
                {
                    "timestamp": point.timestamp,
                    "symbol": point.symbol,
                    "open": point.open,
                    "high": point.high,
                    "low": point.low,
                    "close": point.close,
                    "volume": point.volume,
                    "source": point.source,
                }
                for point in self._points
            ]
        ).set_index("timestamp")
        frame.index = pd.DatetimeIndex(frame.index).tz_convert("UTC")
        return frame

    @classmethod
    def from_dataframe(
        cls,
        frame: pd.DataFrame,
        *,
        symbol: str | None = None,
        source: str | None = None,
    ) -> TimeSeries:
        """Build a TimeSeries from a DataFrame with OHLCV columns and datetime index."""

        required = {"open", "high", "low", "close", "volume"}
        normalized = {str(column).lower(): column for column in frame.columns}
        missing = required - normalized.keys()
        if missing:
            raise ValueError(f"DataFrame is missing required columns: {', '.join(sorted(missing))}")

        points: list[TimeSeriesPoint] = []
        for index, row in frame.iterrows():
            timestamp = pd.Timestamp(index)
            if timestamp.tzinfo is None:
                timestamp = timestamp.tz_localize("UTC")
            else:
                timestamp = timestamp.tz_convert("UTC")

            row_symbol = symbol if symbol is not None else row.get("symbol")
            row_source = source if source is not None else row.get("source")
            if not isinstance(row_symbol, str) or not row_symbol.strip():
                raise ValueError("symbol must be provided or present in the DataFrame")
            if not isinstance(row_source, str) or not row_source.strip():
                raise ValueError("source must be provided or present in the DataFrame")

            points.append(
                TimeSeriesPoint(
                    timestamp=timestamp.to_pydatetime(),
                    symbol=row_symbol.strip().upper(),
                    open=float(row[normalized["open"]]),
                    high=float(row[normalized["high"]]),
                    low=float(row[normalized["low"]]),
                    close=float(row[normalized["close"]]),
                    volume=float(row[normalized["volume"]]),
                    source=row_source,
                )
            )
        return cls(points)
