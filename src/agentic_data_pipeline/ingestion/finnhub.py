"""Free-tier Finnhub REST API ingestion and response normalization."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agentic_data_pipeline.types import MarketQuote

JsonObject = Mapping[str, Any]
Transport = Callable[[str, Mapping[str, str], float], JsonObject]


class FinnhubError(RuntimeError):
    """Base exception for Finnhub ingestion failures."""


class FinnhubConfigurationError(FinnhubError):
    """Raised when the client configuration is invalid."""


class FinnhubApiError(FinnhubError):
    """Raised when Finnhub returns an error or malformed response."""


class FinnhubClient:
    """Read Finnhub's free real-time quote API."""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 10.0,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("FINNHUB_API_KEY", "")).strip()
        if not self.api_key:
            raise FinnhubConfigurationError(
                "A Finnhub API key is required; pass api_key or set FINNHUB_API_KEY"
            )
        if timeout <= 0:
            raise FinnhubConfigurationError("timeout must be greater than zero")
        self.timeout = timeout
        self._transport = transport or self._request_json

    def get_quote(self, symbol: str) -> MarketQuote:
        """Fetch and standardize a real-time US stock quote."""

        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        payload = self._transport(
            f"{self.BASE_URL}/quote",
            {"symbol": normalized_symbol},
            self.timeout,
        )
        return self._normalize_quote(payload, normalized_symbol)

    @staticmethod
    def _normalize_quote(payload: JsonObject, symbol: str) -> MarketQuote:
        if "error" in payload:
            raise FinnhubApiError(str(payload["error"]))
        required = ("c", "h", "l", "o", "pc", "t")
        missing = [key for key in required if payload.get(key) is None]
        if missing:
            raise FinnhubApiError(
                f"quote response is missing required fields: {', '.join(missing)}"
            )
        try:
            timestamp = int(payload["t"])
            if timestamp <= 0:
                raise ValueError("timestamp must be positive")
            return MarketQuote(
                timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc),
                symbol=symbol,
                current_price=float(payload["c"]),
                open=float(payload["o"]),
                high=float(payload["h"]),
                low=float(payload["l"]),
                previous_close=float(payload["pc"]),
                change=_optional_float(payload.get("d")),
                percent_change=_optional_float(payload.get("dp")),
                source="finnhub",
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise FinnhubApiError(f"invalid quote value: {exc}") from exc

    def _request_json(
        self, url: str, params: Mapping[str, str], timeout: float
    ) -> JsonObject:
        request = Request(
            f"{url}?{urlencode(params)}",
            headers={"Accept": "application/json", "X-Finnhub-Token": self.api_key},
        )
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                payload = json.load(response)
        except HTTPError as exc:
            raise FinnhubApiError(f"Finnhub HTTP error {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            detail = exc.reason if isinstance(exc, URLError) else exc
            raise FinnhubApiError(f"Could not reach Finnhub: {detail}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise FinnhubApiError("Finnhub returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise FinnhubApiError("Finnhub response must be a JSON object")
        return payload


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)
