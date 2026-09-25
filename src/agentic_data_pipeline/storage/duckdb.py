"""DuckDB-backed persistence with point-in-time observation history."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from agentic_data_pipeline.types import validate_market_data


class DuckDBStorage:
    """Persist versioned market observations in a local DuckDB database."""

    def __init__(self, path: str | os.PathLike[str] = "data/market.duckdb") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.path))

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    event_timestamp TIMESTAMPTZ NOT NULL,
                    available_timestamp TIMESTAMPTZ NOT NULL,
                    symbol VARCHAR NOT NULL, interval VARCHAR NOT NULL, source VARCHAR NOT NULL,
                    open DOUBLE NOT NULL, high DOUBLE NOT NULL, low DOUBLE NOT NULL,
                    close DOUBLE NOT NULL, volume DOUBLE,
                    PRIMARY KEY (symbol, interval, source, event_timestamp, available_timestamp)
                )
                """)

    def save_market_data(self, frame: pd.DataFrame, *, source: str, interval: str,
                         layer: str = "raw", update: bool = False,
                         available_timestamp: datetime | pd.Timestamp | None = None) -> Path:
        """Append a new available-time version while retaining prior versions."""
        if layer != "raw":
            raise ValueError("DuckDBStorage currently supports the raw layer only")
        validated = validate_market_data(frame.copy())
        symbol = str(validated.attrs["symbol"]).strip().upper()
        available = pd.Timestamp(available_timestamp or datetime.now(UTC))
        available = available.tz_localize("UTC") if available.tzinfo is None else available.tz_convert("UTC")
        records = validated.reset_index().rename(columns={"timestamp": "event_timestamp"})
        records["available_timestamp"] = available
        records["symbol"] = symbol
        records["interval"] = interval
        records["source"] = source
        records = records[["event_timestamp", "available_timestamp", "symbol", "interval",
                           "source", "open", "high", "low", "close", "volume"]]
        with self._connect() as connection:
            connection.register("_incoming_market_data", records)
            connection.execute("INSERT OR IGNORE INTO market_data SELECT * FROM _incoming_market_data")
            connection.unregister("_incoming_market_data")
        return self.path

    def load_market_data(self, *, source: str, interval: str, symbol: str, layer: str = "raw",
                         as_of: datetime | pd.Timestamp | None = None,
                         history: bool = False) -> pd.DataFrame:
        """Load latest observations or reconstruct data at an available-time cutoff."""
        if layer != "raw":
            raise ValueError("DuckDBStorage currently supports the raw layer only")
        normalized_symbol = symbol.strip().upper()
        where = "symbol = ? AND interval = ? AND source = ?"
        parameters: list[object] = [normalized_symbol, interval, source]
        if as_of is not None:
            cutoff = pd.Timestamp(as_of)
            cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
            where += " AND available_timestamp <= ?"
            parameters.append(cutoff.to_pydatetime())
        if history:
            query = f"SELECT * FROM market_data WHERE {where} ORDER BY event_timestamp, available_timestamp"
        else:
            query = f"""SELECT * EXCLUDE (version_rank) FROM (
                SELECT *, row_number() OVER (PARTITION BY event_timestamp
                ORDER BY available_timestamp DESC) AS version_rank
                FROM market_data WHERE {where}
) WHERE version_rank = 1 ORDER BY event_timestamp"""
        with self._connect() as connection:
            result = connection.execute(query, parameters).fetchdf()
        if result.empty:
            result = pd.DataFrame(columns=["open", "high", "low", "close", "volume", "source",
                                           "available_timestamp"],
                                  index=pd.DatetimeIndex([], tz="UTC", name="event_timestamp"))
        else:
            result["event_timestamp"] = pd.to_datetime(result["event_timestamp"], utc=True)
            result["available_timestamp"] = pd.to_datetime(result["available_timestamp"], utc=True)
            result = result.set_index("event_timestamp")
        result.attrs = {"symbol": normalized_symbol, "interval": interval}
        return result

    def latest_event_timestamp(self, *, source: str, interval: str, symbol: str) -> pd.Timestamp | None:
        """Return the newest persisted event timestamp."""
        with self._connect() as connection:
            row = connection.execute("SELECT max(event_timestamp) FROM market_data WHERE symbol = ? AND interval = ? AND source = ?",
                                     [symbol.strip().upper(), interval, source]).fetchone()
        if row is None or row[0] is None:
            return None
        timestamp = pd.Timestamp(row[0])
        return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")
