"""Historical market-data and cash-distribution ingestion via yfinance."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import pandas as pd
import yfinance as yf

from agentic_data_pipeline.types import create_market_data
from agentic_data_pipeline.corporate_actions import create_corporate_actions
import numpy as np

HistoryLoader = Callable[..., pd.DataFrame]
DistributionLoader = Callable[..., pd.Series | pd.DataFrame]


class YFinanceError(RuntimeError):
    """Raised when yfinance data cannot be retrieved or normalized."""


class YFinanceClient:
    """Fetch historical OHLCV and cash-distribution data through yfinance."""

    def __init__(
        self,
        *,
        history_loader: HistoryLoader | None = None,
        distribution_loader: DistributionLoader | None = None,
    ) -> None:
        self._history_loader = history_loader or self._load_history
        self._distribution_loader = distribution_loader or self._load_distributions

    def get_history(
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

        normalized_symbol = self._normalize_symbol(symbol)
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

    def get_distributions(
        self,
        symbol: str,
        *,
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch per-share cash distributions such as dividends.

        The returned frame uses a UTC ``DatetimeIndex`` named ``timestamp`` and
        the columns ``cash_amount`` and ``source``. An empty frame is valid for
        instruments that made no cash distributions in the requested range.

        ``end`` follows yfinance's usual exclusive-bound convention.
        """

        normalized_symbol = self._normalize_symbol(symbol)
        kwargs: dict[str, Any] = {}
        if start is not None:
            kwargs["start"] = start
        if end is not None:
            kwargs["end"] = end

        try:
            raw = self._distribution_loader(normalized_symbol, **kwargs)
        except Exception as exc:
            raise YFinanceError(
                f"Could not retrieve distributions for {normalized_symbol}: {exc}"
            ) from exc

        if isinstance(raw, pd.DataFrame):
            if "Dividends" in raw.columns:
                amounts = raw["Dividends"]
            elif "cash_amount" in raw.columns:
                amounts = raw["cash_amount"]
            elif raw.empty:
                amounts = pd.Series(dtype=float, index=raw.index)
            else:
                raise YFinanceError(
                    "yfinance distribution response must contain Dividends"
                )
        elif isinstance(raw, pd.Series):
            amounts = raw
        else:
            raise YFinanceError(
                "yfinance distribution response must be a pandas Series or DataFrame"
            )

        if not isinstance(amounts.index, pd.DatetimeIndex):
            raise YFinanceError("yfinance distributions must use a DatetimeIndex")

        numeric = pd.to_numeric(amounts, errors="coerce")
        if numeric.isna().any() or (~np.isfinite(numeric)).any():
            raise YFinanceError("yfinance distributions contain non-numeric values")
        if (numeric < 0).any():
            raise YFinanceError("yfinance distributions must not be negative")

        frame = pd.DataFrame({"cash_amount": numeric.astype(float)})
        frame = frame.loc[frame["cash_amount"] > 0].copy()

        index = pd.DatetimeIndex(frame.index)
        if index.tz is None:
            index = index.tz_localize("UTC")
        else:
            index = index.tz_convert("UTC")
        index.name = "timestamp"
        frame.index = index
        frame = frame.sort_index()
        frame["source"] = "yfinance"
        frame.attrs = {
            "symbol": normalized_symbol,
            "dataset": "distributions",
            "source": "yfinance",
        }
        return frame

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        return normalized_symbol

    @staticmethod
    def _load_history(symbol: str, **kwargs: Any) -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        frame = ticker.history(**kwargs)
        if kwargs.get("actions"):
            frame.attrs["currency"] = ticker.history_metadata.get("currency")
        return frame

    @staticmethod
    def _load_distributions(symbol: str, **kwargs: Any) -> pd.Series:
        history_kwargs: dict[str, Any] = {
            "actions": True,
            "auto_adjust": False,
        }
        if kwargs:
            history_kwargs.update(kwargs)
        else:
            history_kwargs["period"] = "max"
        frame = yf.Ticker(symbol).history(**history_kwargs)
        if frame.empty or "Dividends" not in frame.columns:
            raise YFinanceError("Dividend availability is unknown: no usable history returned")
        return frame["Dividends"]

    def get_actions(
        self, symbol: str, *, period: str = "max",
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
    ) -> pd.DataFrame:
        """Return historical dividends, capital-gains distributions and splits.

        Save with ``ParquetStorage.save_dataset(..., dataset='corporate_actions')``.
        Cash values retain Yahoo's quote units; unknown fields are NaN rather
        than zero. ``end`` is exclusive, following yfinance's history contract.
        """
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        kwargs: dict[str, Any] = {"interval": "1d", "auto_adjust": False, "actions": True}
        if start is not None or end is not None:
            kwargs.update(start=start, end=end)
        else:
            kwargs["period"] = period
        try:
            history = self._history_loader(normalized_symbol, **kwargs)
            if not isinstance(history, pd.DataFrame) or history.empty:
                raise ValueError("No history returned; event availability is unknown")
            return create_corporate_actions(
                history, symbol=normalized_symbol, currency=history.attrs.get("currency")
            )
        except Exception as exc:
            raise YFinanceError(f"Could not retrieve actions for {normalized_symbol}: {exc}") from exc
