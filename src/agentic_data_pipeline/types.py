"""Provider-independent time-series domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class TimeSeriesPoint:
    """A standardized OHLCV observation from any market-data provider.

    Timestamps are always timezone-aware UTC values. Prices are represented as
    floats because upstream market-data APIs encode them as JSON numbers.
    """

    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if self.timestamp.utcoffset() != timezone.utc.utcoffset(self.timestamp):
            raise ValueError("timestamp must use UTC")
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
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if self.timestamp.utcoffset() != timezone.utc.utcoffset(self.timestamp):
            raise ValueError("timestamp must use UTC")
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")

    def to_dict(self) -> dict[str, Any]:
        """Return a serialization-friendly representation of this quote."""

        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat().replace("+00:00", "Z")
        return result
