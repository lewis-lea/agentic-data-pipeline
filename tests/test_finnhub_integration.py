"""Integration tests that exercise the real Finnhub API.

Locally, credentials may be supplied in a .env file. In GitHub Actions the
same FINNHUB_API_KEY variable is populated from a repository secret.
"""

import os

import pytest
from dotenv import load_dotenv

from agentic_data_pipeline.ingestion import FinnhubClient

pytestmark = pytest.mark.integration


def test_get_latest_from_real_finnhub_api() -> None:
    """Fetch real market data using credentials supplied by the environment."""

    load_dotenv()
    if not os.getenv("FINNHUB_API_KEY"):
        pytest.skip("FINNHUB_API_KEY is not configured")

    frame = FinnhubClient().get_latest("AAPL")

    assert frame.attrs["symbol"] == "AAPL"
    assert frame.iloc[0]["source"] == "finnhub"
    assert frame.iloc[0]["close"] >= 0
    assert frame.iloc[0]["high"] >= frame.iloc[0]["low"]
