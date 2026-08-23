"""Tests for free-tier Finnhub ingestion and normalization."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from agentic_data_pipeline.ingestion.finnhub import FinnhubApiError, FinnhubClient


def test_get_latest_normalizes_response() -> None:
    captured: dict[str, object] = {}

    def transport(url: str, params: dict[str, str], timeout: float) -> dict[str, object]:
        captured.update(url=url, params=params, timeout=timeout)
        return {
            "c": 130.25, "d": 2.5, "dp": 1.96, "h": 131.0, "l": 127.5,
            "o": 128.0, "pc": 127.75, "t": 1_700_000_000,
        }

    frame = FinnhubClient("secret", timeout=3, transport=transport).get_latest(" nvda ")

    assert isinstance(frame, pd.DataFrame)
    assert list(frame.columns) == ["open", "high", "low", "close", "volume", "source"]
    assert frame.attrs["symbol"] == "NVDA"
    assert frame.attrs["previous_close"] == 127.75
    assert frame.attrs["change"] == 2.5
    assert frame.iloc[0]["close"] == 130.25
    assert frame.iloc[0]["source"] == "finnhub"
    assert pd.isna(frame.iloc[0]["volume"])
    assert frame.index[0] == pd.Timestamp(
        datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)
    )
    assert captured == {
        "url": "https://finnhub.io/api/v1/quote",
        "params": {"symbol": "NVDA"},
        "timeout": 3,
    }


def test_get_quote_is_compatibility_alias() -> None:
    payload = {"c": 10, "h": 11, "l": 9, "o": 9.5, "pc": 9.75, "t": 1_700_000_000}
    client = FinnhubClient("secret", transport=lambda _url, _params, _timeout: payload)

    assert client.get_quote("NVDA").equals(client.get_latest("NVDA"))


def test_get_latest_rejects_incomplete_response() -> None:
    client = FinnhubClient("secret", transport=lambda _url, _params, _timeout: {"c": 10})

    with pytest.raises(FinnhubApiError, match="missing required fields"):
        client.get_latest("NVDA")


def test_get_latest_rejects_provider_error() -> None:
    client = FinnhubClient(
        "secret", transport=lambda _url, _params, _timeout: {"error": "bad symbol"}
    )

    with pytest.raises(FinnhubApiError, match="bad symbol"):
        client.get_latest("NVDA")


def test_get_latest_rejects_empty_symbol() -> None:
    client = FinnhubClient("secret", transport=lambda _url, _params, _timeout: {})

    with pytest.raises(ValueError, match="symbol must not be empty"):
        client.get_latest("  ")
