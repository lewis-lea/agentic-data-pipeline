"""Helpers for exporting static dashboard data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from agentic_data_pipeline.returns import build_return_history


def build_dashboard_series(
    market_data: pd.DataFrame,
    distributions: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Serialize one instrument's price and total-return history for the web UI."""

    history = build_return_history(market_data, distributions)
    records: list[dict[str, Any]] = []
    for timestamp, row in history.iterrows():
        records.append(
            {
                "date": pd.Timestamp(timestamp).date().isoformat(),
                "price": float(row["price"]),
                "distribution": float(row["cash_distribution"]),
                "price_index": float(row["price_index"]),
                "total_return_index": float(row["total_return_index"]),
            }
        )
    return records


def build_dashboard_payload(
    instruments: list[dict[str, Any]],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Wrap serialized instrument records with stable dashboard metadata."""

    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)

    return {
        "generated_at": timestamp.isoformat(),
        "instruments": instruments,
    }
