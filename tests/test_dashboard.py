"""Tests for dashboard serialization helpers."""

from datetime import datetime, timezone

import pandas as pd

from agentic_data_pipeline.dashboard import build_dashboard_payload, build_dashboard_series


def test_build_dashboard_series_serializes_price_distribution_and_total_return() -> None:
    market = pd.DataFrame(
        {"close": [100.0, 95.0]},
        index=pd.DatetimeIndex(
            ["2026-01-01", "2026-01-02"], tz="UTC", name="timestamp"
        ),
    )
    distributions = pd.DataFrame(
        {"cash_amount": [5.0]},
        index=pd.DatetimeIndex(["2026-01-02"], tz="UTC", name="timestamp"),
    )

    records = build_dashboard_series(market, distributions)

    assert records == [
        {
            "date": "2026-01-01",
            "price": 100.0,
            "distribution": 0.0,
            "price_index": 100.0,
            "total_return_index": 100.0,
        },
        {
            "date": "2026-01-02",
            "price": 95.0,
            "distribution": 5.0,
            "price_index": 95.0,
            "total_return_index": 100.0,
        },
    ]


def test_build_dashboard_payload_normalizes_timestamp_to_utc() -> None:
    payload = build_dashboard_payload(
        [{"symbol": "ABC", "series": []}],
        generated_at=datetime(2026, 1, 1, 12, 30),
    )
    assert payload["generated_at"] == "2026-01-01T12:30:00+00:00"
    assert payload["instruments"][0]["symbol"] == "ABC"

    aware = build_dashboard_payload(
        [],
        generated_at=datetime(2026, 1, 1, 13, 30, tzinfo=timezone.utc),
    )
    assert aware["generated_at"].endswith("+00:00")


def test_build_dashboard_payload_uses_current_time_when_not_supplied() -> None:
    payload = build_dashboard_payload([])
    parsed = datetime.fromisoformat(payload["generated_at"])
    assert parsed.tzinfo is not None
