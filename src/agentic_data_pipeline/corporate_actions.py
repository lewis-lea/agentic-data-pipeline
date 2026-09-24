"""Canonical historical cash distributions and stock-split events."""

from __future__ import annotations

import numpy as np
import pandas as pd

ACTION_COLUMNS = {"Dividends": "dividends", "Capital Gains": "capital_gains",
                  "Stock Splits": "stock_splits"}


def create_corporate_actions(
    history: pd.DataFrame, *, symbol: str, currency: str | None = None,
) -> pd.DataFrame:
    """Extract Yahoo events using exchange-local dates and provider quote units.

    Dividends/capital gains are cash amounts per share as reported by Yahoo,
    normally on the ex-date (not the payment date). Splits are new/old share
    ratios, not income. Missing provider columns remain unknown (NaN).
    """
    if not isinstance(history, pd.DataFrame) or not isinstance(history.index, pd.DatetimeIndex):
        raise ValueError("Corporate actions require a dated history DataFrame")
    if not symbol.strip():
        raise ValueError("symbol must not be empty")
    result = pd.DataFrame(index=history.index)
    for source, target in ACTION_COLUMNS.items():
        result[target] = (pd.to_numeric(history[source], errors="raise")
                          if source in history else np.nan)
    values = result.to_numpy(dtype=float)
    if np.isinf(values).any() or (values < 0).any():
        raise ValueError("Corporate-action values must be finite and non-negative")
    result = result.loc[result.fillna(0).ne(0).any(axis=1)]
    if result.index.isna().any():
        raise ValueError("Corporate-action dates must be valid")
    # Encode a trading-date label as UTC midnight, without shifting its date.
    result.index = pd.DatetimeIndex(result.index.date, tz="UTC", name="date")
    result = result[~result.index.duplicated(keep="last")].sort_index()
    result.attrs = {"symbol": symbol.strip().upper(), "source": "yfinance",
                    "currency": currency, "date_semantics": "exchange-local event/ex-date",
                    "value_basis": "Yahoo-reported per-share amounts; may be split-adjusted",
                    "available_fields": [target for source, target in ACTION_COLUMNS.items()
                                         if source in history]}
    return result
