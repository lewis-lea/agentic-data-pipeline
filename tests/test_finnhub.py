"""Tests for free-tier Finnhub ingestion and normalization."""

from datetime import datetime, timezone

import pytest

from agentic_data_pipeline.ingestion.finnhub import FinnhubApiError, FinnhubClient


def test_get_quote_normalizes_response() -> None:
    captured: dict[str, object] = {}

    def transport(url: str, params: dict[str, str], timeout: float) -> dict[str, object]:
        captured.update(url=url, params=params, timeout=timeout)
        return {
            "c": 130.25, "d": 2.5, "dp": 1.96, "h": 131.0, "l": 127.5,
            "o": 128.0, "pc": 127.75, "t": 1_700_000_000,
        }

    quote = FinnhubClient("secret", timeout=3, transport=transport).get_quote(" nvda ")

    assert quote.symbol == "NVDA"
    assert quote.current_price == 130.25
    assert quote.change == 2.5
    assert quote.timestamp == datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)
    assert quote.source == "finnhub"
    assert captured == {
        "url": "https://finnhub.io/api/v1/quote",
        "params": {"symbol": "NVDA"},
        "timeout": 3,
    }


def test_get_quote_allows_omitted_optional_change_fields() -> None:
    client = FinnhubClient("secret", transport=lambda _url, _params, _timeout: {
        "c": 10, "h": 11, "l": 9, "o": 9.5, "pc": 9.75, "t": 1_700_000_000,
    })

    quote = client.get_quote("NVDA")

    assert quote.change is None
    assert quote.percent_change is None


def test_get_quote_rejects_incomplete_response() -> None:
    client = FinnhubClient("secret", transport=lambda _url, _params, _timeout: {"c": 10})

    with pytest.raises(FinnhubApiError, match="missing required fields"):
        client.get_quote("NVDA")


def test_get_quote_rejects_provider_error() -> None:
    client = FinnhubClient(
        "secret", transport=lambda _url, _params, _timeout: {"error": "bad symbol"}
    )

    with pytest.raises(FinnhubApiError, match="bad symbol"):
        client.get_quote("NVDA")


def test_get_quote_rejects_empty_symbol() -> None:
    client = FinnhubClient("secret", transport=lambda _url, _params, _timeout: {})

    with pytest.raises(ValueError, match="symbol must not be empty"):
        client.get_quote("  ")
