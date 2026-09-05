"""Return-series construction from prices and explicit cash distributions."""

from __future__ import annotations

import numpy as np
import pandas as pd


def build_return_history(
    market_data: pd.DataFrame,
    distributions: pd.DataFrame | None = None,
    *,
    base: float = 100.0,
) -> pd.DataFrame:
    """Build price and reinvested total-return indices.

    ``market_data`` must contain a positive ``close`` column on a sorted
    ``DatetimeIndex``. ``distributions`` may contain a ``cash_amount`` column
    representing cash paid per share/unit. Cash is aligned to the first market
    observation at or after its timestamp, which is robust to small timestamp
    differences between yfinance price and corporate-action series.

    The total-return calculation assumes each distribution is reinvested at the
    closing price on the aligned distribution date. This is a transparent
    approximation suitable for comparing historical return paths; it does not
    model tax, dealing costs, withholding tax, or reinvestment slippage.
    """

    if not isinstance(market_data, pd.DataFrame):
        raise TypeError("market_data must be a pandas DataFrame")
    if not isinstance(market_data.index, pd.DatetimeIndex):
        raise ValueError("market_data must use a DatetimeIndex")
    if "close" not in market_data.columns:
        raise ValueError("market_data must contain a close column")
    if market_data.empty:
        raise ValueError("market_data must contain at least one observation")
    if not np.isfinite(base) or base <= 0:
        raise ValueError("base must be a positive finite number")

    market = market_data.sort_index()
    close = pd.to_numeric(market["close"], errors="coerce").astype(float)
    if close.isna().any() or (~np.isfinite(close)).any() or (close <= 0).any():
        raise ValueError("market_data close values must be positive and finite")

    cash = pd.Series(0.0, index=market.index, dtype=float)
    cash.index.name = market.index.name

    if distributions is not None:
        if not isinstance(distributions, pd.DataFrame):
            raise TypeError("distributions must be a pandas DataFrame")
        if not isinstance(distributions.index, pd.DatetimeIndex):
            raise ValueError("distributions must use a DatetimeIndex")
        if "cash_amount" not in distributions.columns:
            raise ValueError("distributions must contain a cash_amount column")

        if not distributions.empty:
            amounts = pd.to_numeric(distributions["cash_amount"], errors="coerce")
            if amounts.isna().any() or (~np.isfinite(amounts)).any() or (amounts < 0).any():
                raise ValueError("cash_amount values must be non-negative and finite")

            grouped = amounts.groupby(distributions.index).sum().sort_index()
            for timestamp, amount in grouped.items():
                position = market.index.searchsorted(timestamp, side="left")
                if position < len(market.index):
                    cash.iloc[position] += float(amount)

    price_index = close / close.iloc[0] * base
    period_return = (close + cash) / close.shift(1) - 1.0
    period_return.iloc[0] = 0.0
    total_return_index = (1.0 + period_return).cumprod() * base

    result = pd.DataFrame(
        {
            "price": close,
            "cash_distribution": cash,
            "price_index": price_index,
            "total_return_index": total_return_index,
        },
        index=market.index,
    )
    result.attrs = dict(market_data.attrs)
    result.attrs["return_base"] = float(base)
    result.attrs["distribution_assumption"] = "reinvest_at_aligned_close"
    return result
