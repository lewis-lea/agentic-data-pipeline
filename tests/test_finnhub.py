"""Tests for Finnhub ingestion and normalization."""

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


def test_get_recommendation_trends_normalizes_monthly_series() -> None:
    payload = [
        {"buy": 4, "hold": 2, "period": "2026-07-01", "sell": 1, "strongBuy": 3, "strongSell": 0},
        {"buy": 5, "hold": 1, "period": "2026-08-01", "sell": 0, "strongBuy": 4, "strongSell": 0},
    ]
    client = FinnhubClient("secret", transport=lambda _url, _params, _timeout: payload)

    frame = client.get_recommendation_trends("nvda")

    assert frame.attrs == {"symbol": "NVDA", "frequency": "monthly"}
    assert list(frame.columns) == [
        "strong_buy", "buy", "hold", "sell", "strong_sell",
        "analyst_count", "analyst_sentiment", "source",
    ]
    assert frame.index.tz is not None
    assert frame.loc[pd.Timestamp("2026-08-01", tz="UTC"), "analyst_count"] == 10
    assert frame.loc[pd.Timestamp("2026-08-01", tz="UTC"), "analyst_sentiment"] == pytest.approx(0.65)


def test_get_insider_sentiment_normalizes_monthly_series() -> None:
    captured: dict[str, object] = {}

    def transport(url: str, params: dict[str, str], timeout: float) -> dict[str, object]:
        captured.update(url=url, params=params, timeout=timeout)
        return {
            "symbol": "NVDA",
            "data": [
                {"year": 2026, "month": 7, "change": -1200, "mspr": -18.5},
                {"year": 2026, "month": 8, "change": 500, "mspr": 12.25},
            ],
        }

    frame = FinnhubClient("secret", transport=transport).get_insider_sentiment(
        "nvda", start="2026-07-01", end="2026-08-31"
    )

    assert frame.attrs == {"symbol": "NVDA", "frequency": "monthly"}
    assert list(frame.columns) == ["mspr", "change", "source"]
    assert frame.loc[pd.Timestamp("2026-08-01", tz="UTC"), "mspr"] == 12.25
    assert captured["params"] == {
        "symbol": "NVDA", "from": "2026-07-01", "to": "2026-08-31"
    }


def test_get_social_sentiment_normalizes_series() -> None:
    captured: dict[str, object] = {}

    def transport(url: str, params: dict[str, str], timeout: float) -> dict[str, object]:
        captured.update(url=url, params=params, timeout=timeout)
        return {
            "symbol": "GME",
            "data": [
                {
                    "atTime": "2026-08-20 14:00:00",
                    "mention": 32,
                    "positiveMention": 20,
                    "negativeMention": 12,
                    "positiveScore": 0.92,
                    "negativeScore": -0.98,
                    "score": -0.03,
                }
            ],
        }

    frame = FinnhubClient("secret", transport=transport).get_social_sentiment(
        "gme", start="2026-08-20", end="2026-08-21"
    )

    assert frame.attrs == {"symbol": "GME", "dataset": "social_sentiment"}
    assert list(frame.columns) == [
        "mention", "positive_mention", "negative_mention", "positive_score",
        "negative_score", "sentiment_score", "source",
    ]
    assert frame.iloc[0]["mention"] == 32
    assert frame.iloc[0]["sentiment_score"] == pytest.approx(-0.03)
    assert str(frame.index.tz) == "UTC"
    assert captured["url"] == "https://finnhub.io/api/v1/stock/social-sentiment"
    assert captured["params"] == {
        "symbol": "GME", "from": "2026-08-20", "to": "2026-08-21"
    }


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
