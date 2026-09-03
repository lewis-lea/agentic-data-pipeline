"""Finnhub REST API ingestion and response normalization."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from agentic_data_pipeline.types import create_market_data

JsonObject = Mapping[str, Any]
JsonPayload = JsonObject | Sequence[JsonObject]
Transport = Callable[[str, Mapping[str, str], float], JsonPayload]


class FinnhubError(RuntimeError):
    """Base exception for Finnhub ingestion failures."""


class FinnhubConfigurationError(FinnhubError):
    """Raised when the client configuration is invalid."""


class FinnhubApiError(FinnhubError):
    """Raised when Finnhub returns an error or malformed response."""


class FinnhubClient:
    """Read Finnhub market and qualitative-data APIs."""

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

    def get_latest(self, symbol: str) -> pd.DataFrame:
        """Fetch the latest quote as a one-row canonical market-data DataFrame."""

        normalized_symbol = self._normalize_symbol(symbol)
        payload = self._transport(
            f"{self.BASE_URL}/quote",
            {"symbol": normalized_symbol},
            self.timeout,
        )
        if not isinstance(payload, Mapping):
            raise FinnhubApiError("quote response must be a JSON object")
        return self._normalize_quote(payload, normalized_symbol)

    def get_quote(self, symbol: str) -> pd.DataFrame:
        """Compatibility alias for :meth:`get_latest`."""

        return self.get_latest(symbol)

    def get_recommendation_trends(self, symbol: str) -> pd.DataFrame:
        """Fetch monthly analyst recommendation counts and a normalized score.

        The returned frame is indexed by the recommendation period and contains
        ``strong_buy``, ``buy``, ``hold``, ``sell``, ``strong_sell``,
        ``analyst_count``, ``analyst_sentiment`` and ``source``. The sentiment
        score ranges from -1 (all strong sell) to +1 (all strong buy).
        """

        normalized_symbol = self._normalize_symbol(symbol)
        payload = self._transport(
            f"{self.BASE_URL}/stock/recommendation",
            {"symbol": normalized_symbol},
            self.timeout,
        )
        if isinstance(payload, Mapping):
            if "error" in payload:
                raise FinnhubApiError(str(payload["error"]))
            raise FinnhubApiError("recommendation response must be a JSON array")
        return self._normalize_recommendations(payload, normalized_symbol)

    def get_insider_sentiment(
        self,
        symbol: str,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Fetch Finnhub's monthly insider-sentiment MSPR series."""

        normalized_symbol = self._normalize_symbol(symbol)
        params = {"symbol": normalized_symbol}
        if start is not None:
            params["from"] = start
        if end is not None:
            params["to"] = end
        payload = self._transport(
            f"{self.BASE_URL}/stock/insider-sentiment",
            params,
            self.timeout,
        )
        if not isinstance(payload, Mapping):
            raise FinnhubApiError("insider sentiment response must be a JSON object")
        return self._normalize_insider_sentiment(payload, normalized_symbol)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        return normalized_symbol

    @staticmethod
    def _normalize_quote(payload: JsonObject, symbol: str) -> pd.DataFrame:
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
            index = pd.DatetimeIndex(
                [datetime.fromtimestamp(timestamp, tz=timezone.utc)],
                name="timestamp",
            )
            raw = pd.DataFrame(
                {
                    "open": [float(payload["o"])],
                    "high": [float(payload["h"])],
                    "low": [float(payload["l"])],
                    "close": [float(payload["c"])],
                    "volume": [float("nan")],
                },
                index=index,
            )
            return create_market_data(
                raw,
                symbol=symbol,
                source="finnhub",
                metadata={
                    "previous_close": float(payload["pc"]),
                    "change": _optional_float(payload.get("d")),
                    "percent_change": _optional_float(payload.get("dp")),
                },
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise FinnhubApiError(f"invalid quote value: {exc}") from exc

    @staticmethod
    def _normalize_recommendations(
        payload: Sequence[JsonObject], symbol: str
    ) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        index: list[pd.Timestamp] = []
        try:
            for item in payload:
                period = item.get("period")
                if not isinstance(period, str) or not period.strip():
                    raise ValueError("period is missing")
                counts = {
                    "strong_buy": int(item.get("strongBuy", 0)),
                    "buy": int(item.get("buy", 0)),
                    "hold": int(item.get("hold", 0)),
                    "sell": int(item.get("sell", 0)),
                    "strong_sell": int(item.get("strongSell", 0)),
                }
                if any(value < 0 for value in counts.values()):
                    raise ValueError("recommendation counts must not be negative")
                analyst_count = sum(counts.values())
                weighted = (
                    2 * counts["strong_buy"]
                    + counts["buy"]
                    - counts["sell"]
                    - 2 * counts["strong_sell"]
                )
                sentiment = weighted / (2 * analyst_count) if analyst_count else float("nan")
                rows.append(
                    {
                        **counts,
                        "analyst_count": analyst_count,
                        "analyst_sentiment": sentiment,
                        "source": "finnhub",
                    }
                )
                index.append(pd.Timestamp(period).tz_localize("UTC"))
        except (TypeError, ValueError) as exc:
            raise FinnhubApiError(f"invalid recommendation value: {exc}") from exc

        frame = pd.DataFrame(rows, index=pd.DatetimeIndex(index, name="timestamp")).sort_index()
        frame.attrs = {"symbol": symbol, "frequency": "monthly"}
        return frame

    @staticmethod
    def _normalize_insider_sentiment(payload: JsonObject, symbol: str) -> pd.DataFrame:
        if "error" in payload:
            raise FinnhubApiError(str(payload["error"]))
        data = payload.get("data")
        if not isinstance(data, list):
            raise FinnhubApiError("insider sentiment response is missing data")

        rows: list[dict[str, Any]] = []
        index: list[pd.Timestamp] = []
        try:
            for item in data:
                if not isinstance(item, Mapping):
                    raise ValueError("data item must be an object")
                year = int(item["year"])
                month = int(item["month"])
                rows.append(
                    {
                        "mspr": float(item["mspr"]),
                        "change": float(item["change"]),
                        "source": "finnhub",
                    }
                )
                index.append(pd.Timestamp(year=year, month=month, day=1, tz="UTC"))
        except (KeyError, TypeError, ValueError) as exc:
            raise FinnhubApiError(f"invalid insider sentiment value: {exc}") from exc

        frame = pd.DataFrame(rows, index=pd.DatetimeIndex(index, name="timestamp")).sort_index()
        frame.attrs = {"symbol": symbol, "frequency": "monthly"}
        return frame

    def _request_json(
        self, url: str, params: Mapping[str, str], timeout: float
    ) -> JsonPayload:
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
        if not isinstance(payload, (dict, list)):
            raise FinnhubApiError("Finnhub response must be a JSON object or array")
        return payload


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)
