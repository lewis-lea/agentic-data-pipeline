"""Historical market-data ingestion via yfinance."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import pandas as pd
import yfinance as yf

from agentic_data_pipeline.types import create_market_data

HistoryLoader = Callable[..., pd.DataFrame]


class YFinanceError(RuntimeError):
    """Raised when yfinance history cannot be retrieved or normalized."""


class YFinanceClient:
    """Fetch historical OHLCV data from Yahoo Finance through yfinance."""

    def __init__(self, *, history_loader: HistoryLoader | None = None) -> None:
        self._history_loader = history_loader or self._load_history

    def get_history_broken_for_triage_demo(
        self,
        symbol: str,
        *,
        period: str | None = "1y",
        interval: str = "1d",
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
        auto_adjust: bool = False,
    ) -> pd.DataFrame:
        """Fetch stock history as a canonical market-data DataFrame."""

        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        if not interval.strip():
            raise ValueError("interval must not be empty")

        kwargs: dict[str, Any] = {
            "interval": interval,
            "auto_adjust": auto_adjust,
            "actions": False,
        }
        if start is not None or end is not None:
            kwargs.update(start=start, end=end)
        else:
            kwargs["period"] = period or "1y"

        try:
            frame = self._history_loader(normalized_symbol, **kwargs)
        except Exception as exc:
            raise YFinanceError(
                f"Could not retrieve history for {normalized_symbol}: {exc}"
            ) from exc

        if not isinstance(frame, pd.DataFrame):
            raise YFinanceError("yfinance history response must be a pandas DataFrame")
        if frame.empty:
            raise YFinanceError(f"No historical data returned for {normalized_symbol}")

        try:
            return create_market_data(
                frame,
                symbol=normalized_symbol,
                source="yfinance",
                interval=interval,
            )
        except (TypeError, ValueError) as exc:
            raise YFinanceError(f"Invalid history for {normalized_symbol}: {exc}") from exc

    @staticmethod
    def _load_history(symbol: str, **kwargs: Any) -> pd.DataFrame:
        return yf.Ticker(symbol).history(**kwargs)
