"""Integration tests that exercise the real Finnhub API.

Locally, credentials may be supplied in a .env file. In GitHub Actions the
same FINNHUB_API_KEY variable is populated from a repository secret.
"""

import os

import pytest
from dotenv import load_dotenv

from agentic_data_pipeline.ingestion import FinnhubClient

pytestmark = pytest.mark.integration


def _client() -> FinnhubClient:
    load_dotenv()
    if not os.getenv("FINNHUB_API_KEY"):
        pytest.skip("FINNHUB_API_KEY is not configured")
    return FinnhubClient()


def test_get_latest_from_real_finnhub_api() -> None:
    """Fetch real market data using credentials supplied by the environment."""

    frame = _client().get_latest("AAPL")

    assert frame.attrs["symbol"] == "AAPL"
    assert frame.iloc[0]["source"] == "finnhub"
    assert frame.iloc[0]["close"] >= 0
    assert frame.iloc[0]["high"] >= frame.iloc[0]["low"]


def test_social_sentiment_entitlement() -> None:
    """Probe whether the configured Finnhub key can access social sentiment.

    This intentionally fails if Finnhub rejects the dataset so the CI output
    gives a definitive entitlement result for the configured repository key.
    """

    frame = _client().get_social_sentiment(
        "GME",
        start="2021-05-08",
        end="2021-05-09",
    )

    assert frame.attrs["symbol"] == "GME"
    assert frame.attrs["dataset"] == "social_sentiment"
    assert "sentiment_score" in frame.columns
