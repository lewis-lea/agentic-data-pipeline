"""Incremental ingestion workflows backed by persisted datasets."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from agentic_data_pipeline.ingestion import YFinanceClient
from agentic_data_pipeline.storage import ParquetStorage


def update_yfinance_market_data(
    symbol: str,
    *,
    interval: str = "1d",
    initial_period: str = "5y",
    end: str | date | datetime | None = None,
    auto_adjust: bool = False,
    storage: ParquetStorage | None = None,
    client: YFinanceClient | None = None,
    layer: str = "raw",
) -> pd.DataFrame:
    """Fetch only the latest yfinance range and persist the merged result.

    On the first run, ``initial_period`` is fetched and saved. On later runs,
    ingestion starts at the most recent persisted timestamp. Re-fetching that
    boundary observation is intentional: providers can revise the latest bar,
    and ``ParquetStorage`` resolves duplicate timestamps in favour of the new
    observation.

    The merged persisted DataFrame is returned.
    """

    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    if not interval.strip():
        raise ValueError("interval must not be empty")
    if not initial_period.strip():
        raise ValueError("initial_period must not be empty")

    resolved_storage = storage or ParquetStorage()
    resolved_client = client or YFinanceClient()
    path = resolved_storage.market_data_path(
        source="yfinance",
        interval=interval,
        symbol=normalized_symbol,
        layer=layer,
    )

    if not path.exists():
        initial = resolved_client.get_history(
            normalized_symbol,
            period=initial_period,
            interval=interval,
            end=end,
            auto_adjust=auto_adjust,
        )
        resolved_storage.save_market_data(
            initial,
            source="yfinance",
            interval=interval,
            layer=layer,
        )
        return resolved_storage.load_market_data(
            source="yfinance",
            interval=interval,
            symbol=normalized_symbol,
            layer=layer,
        )

    existing = resolved_storage.load_market_data(
        source="yfinance",
        interval=interval,
        symbol=normalized_symbol,
        layer=layer,
    )
    if existing.empty:
        raise ValueError("persisted market data must contain at least one observation")

    start = existing.index.max()
    if end is not None:
        end_timestamp = pd.Timestamp(end)
        if end_timestamp.tzinfo is None:
            end_timestamp = end_timestamp.tz_localize("UTC")
        else:
            end_timestamp = end_timestamp.tz_convert("UTC")
        if end_timestamp <= start:
            return existing

    latest = resolved_client.get_history(
        normalized_symbol,
        period=None,
        interval=interval,
        start=start,
        end=end,
        auto_adjust=auto_adjust,
    )
    resolved_storage.save_market_data(
        latest,
        source="yfinance",
        interval=interval,
        layer=layer,
        update=True,
    )
    return resolved_storage.load_market_data(
        source="yfinance",
        interval=interval,
        symbol=normalized_symbol,
        layer=layer,
    )
