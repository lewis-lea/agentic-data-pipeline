"""Reproducible, fictional company histories; no downloaded data or calibration."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import pandas as pd

GENERATOR_VERSION = "2"
SEED = 2502026
START, END = "2016-01-04", "2025-12-31"
# Authored GBP starting levels, relative pre-distribution annual trend anchors,
# annual cash yields and daily idiosyncratic volatility. These are assumptions,
# not observations of the named companies or estimates of future performance.
PROFILES = {
    "SIM-A": (10.0, [1, 1.05, 1.25, 1.25, 2.2, 2.0, 2.9, 2.4, 2.9, 3.2, 2.2], 0.025, 0.013),
    "SIM-B": (8.0, [1, 0.95, 0.85, 0.75, 1.2, 1.45, 1.65, 1.3, 1.65, 1.75, 1.65], 0.04, 0.012),
    "SIM-C": (3.0, [1, 1.1, 1.5, 2.1, 3.2, 4.8, 6.3, 4.9, 5.6, 6.6, 7.2], 0.02, 0.014),
    "SIM-D": (4.0, [1, 0.85, 0.6, 0.38, 0.4, 0.35, 0.4, 0.23, 0.2, 0.3, 0.4], 0.015, 0.018),
    "SIM-E": (13.0, [1, 1.2, 1.4, 1.45, 1.4, 1.5, 1.55, 1.3, 1.4, 1.2, 0.95], 0.035, 0.012),
    "SIM-F": (4.0, [1, 1.1, 1.2, 1.1, 1.6, 1.65, 1.9, 1.6, 1.75, 1.9, 1.85], 0.015, 0.011),
}


def _noise(rng: np.random.Generator, size: int, sigma: float) -> np.ndarray:
    """Mean-reverting log-price deviations with fixed endpoints."""
    values = np.zeros(size)
    for index in range(1, size):
        values[index] = 0.96 * values[index - 1] + rng.normal(0, sigma)
    return values - np.linspace(values[0], values[-1], size)


def generate_histories(seed: int = SEED) -> dict[str, pd.DataFrame]:
    """Generate weekday observations with correlated shocks and fictional cash.

    A price drops by the simulated cash amount on each ex-date. The total-return
    index reinvests at that day's close: TR[t]/TR[t-1]=(P[t]+D[t])/P[t-1].
    Adjusted closes are scaled to finish at the final raw close. No splits are
    simulated. Weekdays are a simplified calendar, not an exchange holiday list.
    """
    dates = pd.bdate_range(START, END)
    x = np.arange(len(dates))
    anchors = pd.to_datetime([START] + [f"{year}-12-31" for year in range(2016, 2026)])
    anchor_ns = anchors.to_numpy(dtype="datetime64[ns]").astype("int64")
    date_ns = dates.to_numpy(dtype="datetime64[ns]").astype("int64")
    positions = np.interp(anchor_ns, date_ns, x)
    common = _noise(np.random.default_rng(seed), len(dates), 0.006)
    # Authored abrupt downturn/recovery and a later inflation-like drawdown.
    shock_dates = pd.to_datetime(
        [
            START,
            "2020-02-19",
            "2020-03-23",
            "2021-03-01",
            "2022-01-03",
            "2022-10-03",
            "2023-07-03",
            END,
        ]
    )
    shock_ns = shock_dates.to_numpy(dtype="datetime64[ns]").astype("int64")
    shocks = np.interp(date_ns, shock_ns, [0, 0, -0.42, 0, 0, -0.18, 0, 0])
    result = {}
    for symbol, (initial, levels, cash_yield, sigma) in PROFILES.items():
        # Stable per-symbol streams: reordering/adding profiles cannot perturb others.
        offset = int.from_bytes(hashlib.sha256(symbol.encode()).digest()[:4], "big")
        rng = np.random.default_rng(np.random.SeedSequence([seed, offset]))
        latent = initial * np.exp(
            np.interp(x, positions, np.log(levels))
            + common
            + _noise(rng, len(dates), sigma)
            + shocks
        )
        cash = np.zeros(len(dates))
        prices = latent.copy()
        payout_factor = 1.0
        for index, day in enumerate(dates):
            prices[index] = latent[index] * payout_factor
            # Two fictional ex-dates annually; suspension through the shock year.
            if (
                day.month in (5, 11)
                and day.year != 2020
                and day == pd.Timestamp(day.year, day.month, 15) + pd.offsets.BDay(0)
            ):
                cash[index] = prices[index] * cash_yield / 2
                prices[index] -= cash[index]
                payout_factor *= 1 - cash_yield / 2
        growth = np.ones(len(dates))
        growth[1:] = (prices[1:] + cash[1:]) / prices[:-1]
        total = np.cumprod(growth)
        adjusted = total / total[-1] * prices[-1]
        result[symbol] = pd.DataFrame(
            {
                "Close": prices,
                "Adj Close": adjusted,
                "Dividends": cash,
                "Capital Gains": 0.0,
                "Stock Splits": 0.0,
            },
            index=dates,
        )
    return result


def build_synthetic_snapshot(catalogue: dict[str, Any], *, seed: int = SEED) -> dict[str, Any]:
    """Use the dashboard contract with explicit simulation provenance throughout."""
    from agentic_data_pipeline.dashboard import build_snapshot

    unknown = {item.get("symbol") for item in catalogue["instruments"]} - PROFILES.keys()
    if unknown:
        raise ValueError(f"No synthetic profile for: {sorted(map(str, unknown))}")
    histories = generate_histories(seed)
    snapshot = build_snapshot(
        catalogue, loader=lambda symbol: (histories[symbol], {"currency": "GBP"})
    )
    snapshot.update(
        data_source="synthetic",
        synthetic=True,
        price_basis="Fictional GBP closes; simulated cash distributions excluded",
        sources=["Authored simulation; no market data downloaded"],
        simulation={
            "version": GENERATOR_VERSION,
            "seed": seed,
            "start": START,
            "end": END,
            "calendar": "weekdays, including exchange holidays",
            "method": "Authored trends + correlated mean-reverting noise + shocks + cash distributions",
            "calibration": "None; not fitted to Yahoo or other historical price data",
            "profiles": {
                symbol: {
                    "initial_gbp": profile[0],
                    "trend_anchors": profile[1],
                    "annual_cash_yield": profile[2],
                    "daily_noise": profile[3],
                }
                for symbol, profile in PROFILES.items()
            },
        },
    )
    for item in snapshot["instruments"]:
        item.update(data_source="synthetic", synthetic=True, fetched_at=None)
    return snapshot
