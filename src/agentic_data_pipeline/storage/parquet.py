"""Local Parquet-backed persistence for pipeline datasets."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from agentic_data_pipeline.types import validate_market_data

SCHEMA_VERSION = 1
DEFAULT_DATA_ROOT = "data"


@dataclass(frozen=True)
class DatasetKey:
    """Identify a persisted dataset independently of its filesystem path."""

    source: str
    dataset: str
    symbol: str
    interval: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("source", "dataset", "symbol"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.interval is not None and not self.interval.strip():
            raise ValueError("interval must not be empty")

    @property
    def normalized_symbol(self) -> str:
        return self.symbol.strip().upper()


class ParquetStorage:
    """Persist pipeline datasets as Parquet plus JSON sidecar metadata.

    Market data is stored using an interval-first layout::

        raw/<source>/<interval>/<symbol>.parquet

    Qualitative datasets are stored by dataset name::

        raw/<source>/<dataset>/<symbol>.parquet

    ``root`` defaults to ``AGENTIC_DATA_ROOT`` and then ``./data``.
    """

    def __init__(self, root: str | os.PathLike[str] | None = None) -> None:
        configured_root = root or os.getenv("AGENTIC_DATA_ROOT") or DEFAULT_DATA_ROOT
        self.root = Path(configured_root)

    def market_data_path(
        self,
        *,
        source: str,
        interval: str,
        symbol: str,
        layer: str = "raw",
    ) -> Path:
        key = DatasetKey(source=source, dataset="market_data", symbol=symbol, interval=interval)
        return self._market_path(key, layer=layer)

    def dataset_path(
        self,
        *,
        source: str,
        dataset: str,
        symbol: str,
        layer: str = "raw",
    ) -> Path:
        key = DatasetKey(source=source, dataset=dataset, symbol=symbol)
        return self._qualitative_path(key, layer=layer)

    def save_market_data(
        self,
        frame: pd.DataFrame,
        *,
        source: str,
        interval: str,
        layer: str = "raw",
        update: bool = False,
    ) -> Path:
        """Validate and persist canonical market data.

        When ``update=True``, an existing file is merged with the new frame,
        duplicate timestamps are replaced by the newest observation, and the
        result is sorted by timestamp.
        """

        frame = validate_market_data(frame.copy())
        symbol = str(frame.attrs["symbol"]).strip().upper()
        key = DatasetKey(source=source, dataset="market_data", symbol=symbol, interval=interval)
        path = self._market_path(key, layer=layer)

        if update and path.exists():
            existing = self.load_market_data(
                source=source,
                interval=interval,
                symbol=symbol,
                layer=layer,
            )
            attrs = dict(existing.attrs)
            attrs.update(frame.attrs)
            frame = pd.concat([existing, frame])
            frame = frame[~frame.index.duplicated(keep="last")].sort_index()
            frame.attrs = attrs
            frame = validate_market_data(frame)

        frame.attrs["symbol"] = symbol
        frame.attrs["interval"] = interval
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path)
        self._write_metadata(path, frame, key, layer=layer)
        return path

    def load_market_data(
        self,
        *,
        source: str,
        interval: str,
        symbol: str,
        layer: str = "raw",
    ) -> pd.DataFrame:
        key = DatasetKey(source=source, dataset="market_data", symbol=symbol, interval=interval)
        path = self._market_path(key, layer=layer)
        frame = pd.read_parquet(path)
        metadata = self._read_metadata(path)
        frame.attrs = dict(metadata.get("dataframe_attrs", {}))
        frame.attrs["symbol"] = key.normalized_symbol
        frame.attrs["interval"] = interval
        return validate_market_data(frame)

    def save_dataset(
        self,
        frame: pd.DataFrame,
        *,
        source: str,
        dataset: str,
        symbol: str | None = None,
        layer: str = "raw",
        update: bool = False,
    ) -> Path:
        """Persist a qualitative/time-indexed DataFrame.

        The frame must use a ``DatetimeIndex``. A symbol may be supplied
        explicitly or read from ``frame.attrs['symbol']``.
        """

        if not isinstance(frame, pd.DataFrame):
            raise TypeError("frame must be a pandas DataFrame")
        if not isinstance(frame.index, pd.DatetimeIndex):
            raise ValueError("dataset must use a DatetimeIndex")

        resolved_symbol = (symbol or frame.attrs.get("symbol") or "").strip().upper()
        if not resolved_symbol:
            raise ValueError("symbol must be provided or present in DataFrame.attrs")

        frame = frame.copy().sort_index()
        frame.attrs = dict(frame.attrs)
        frame.attrs["symbol"] = resolved_symbol
        key = DatasetKey(source=source, dataset=dataset, symbol=resolved_symbol)
        path = self._qualitative_path(key, layer=layer)

        if update and path.exists():
            existing = self.load_dataset(
                source=source,
                dataset=dataset,
                symbol=resolved_symbol,
                layer=layer,
            )
            attrs = dict(existing.attrs)
            attrs.update(frame.attrs)
            frame = pd.concat([existing, frame])
            frame = frame[~frame.index.duplicated(keep="last")].sort_index()
            frame.attrs = attrs

        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path)
        self._write_metadata(path, frame, key, layer=layer)
        return path

    def load_dataset(
        self,
        *,
        source: str,
        dataset: str,
        symbol: str,
        layer: str = "raw",
    ) -> pd.DataFrame:
        key = DatasetKey(source=source, dataset=dataset, symbol=symbol)
        path = self._qualitative_path(key, layer=layer)
        frame = pd.read_parquet(path)
        metadata = self._read_metadata(path)
        frame.attrs = dict(metadata.get("dataframe_attrs", {}))
        frame.attrs["symbol"] = key.normalized_symbol
        return frame.sort_index()

    def _market_path(self, key: DatasetKey, *, layer: str) -> Path:
        if key.interval is None:
            raise ValueError("market data requires an interval")
        return (
            self.root
            / self._safe_component(layer)
            / self._safe_component(key.source)
            / self._safe_component(key.interval)
            / f"{self._safe_component(key.normalized_symbol)}.parquet"
        )

    def _qualitative_path(self, key: DatasetKey, *, layer: str) -> Path:
        return (
            self.root
            / self._safe_component(layer)
            / self._safe_component(key.source)
            / self._safe_component(key.dataset)
            / f"{self._safe_component(key.normalized_symbol)}.parquet"
        )

    @staticmethod
    def _safe_component(value: str) -> str:
        normalized = value.strip()
        if not normalized or normalized in {".", ".."}:
            raise ValueError("path component must be non-empty")
        if any(separator in normalized for separator in ("/", "\\")):
            raise ValueError("path components must not contain path separators")
        return normalized

    @staticmethod
    def _metadata_path(path: Path) -> Path:
        return path.with_suffix(".metadata.json")

    def _write_metadata(
        self,
        path: Path,
        frame: pd.DataFrame,
        key: DatasetKey,
        *,
        layer: str,
    ) -> None:
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "source": key.source,
            "dataset": key.dataset,
            "symbol": key.normalized_symbol,
            "interval": key.interval,
            "layer": layer,
            "rows": len(frame),
            "min_timestamp": self._timestamp_or_none(frame.index.min()),
            "max_timestamp": self._timestamp_or_none(frame.index.max()),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "dataframe_attrs": self._json_safe(dict(frame.attrs)),
        }
        self._metadata_path(path).write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )

    def _read_metadata(self, path: Path) -> dict[str, Any]:
        metadata_path = self._metadata_path(path)
        if not metadata_path.exists():
            raise FileNotFoundError(f"metadata sidecar not found: {metadata_path}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported persisted schema version: {metadata.get('schema_version')}"
            )
        return metadata

    @staticmethod
    def _timestamp_or_none(value: object) -> str | None:
        if value is None or pd.isna(value):
            return None
        return pd.Timestamp(value).isoformat()

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._json_safe(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (pd.Timestamp, datetime)):
            return value.isoformat()
        return str(value)
