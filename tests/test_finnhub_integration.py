"""Integration tests that exercise the real Finnhub API.

Locally, credentials may be supplied in a .env file. In GitHub Actions the
same FINNHUB_API_KEY variable is populated from a repository secret.
"""

import os

import pytest
from dotenv import load_dotenv

from agentic_data_pipeline.ingestion import FinnhubClient

pytestmark = pytest.mark.integration


def test_get_quote_from_real_finnhub_api() -> None:
    """Fetch a real quote using credentials supplied by the environment."""

    load_dotenv()
    if not os.getenv("FINNHUB_API_KEY"):
        pytest.skip("FINNHUB_API_KEY is not configured")

    quote = FinnhubClient().get_quote("AAPL")

    assert quote.symbol == "AAPL"
    assert quote.source == "finnhub"
    assert quote.current_price >= 0
    assert quote.high >= quote.low
