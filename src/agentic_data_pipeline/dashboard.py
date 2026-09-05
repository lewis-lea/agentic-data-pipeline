"""Publish close-price snapshots for a static dashboard using only yfinance.

Run ``python -m agentic_data_pipeline.dashboard --help`` for build options.
Funds can provide NAV/close observations without valid OHLC bars, so this
exporter intentionally uses a close-only contract instead of market OHLCV.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import shutil
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from agentic_data_pipeline.corporate_actions import create_corporate_actions
from agentic_data_pipeline.storage import ParquetStorage
from agentic_data_pipeline.returns import build_return_history

LOGGER = logging.getLogger(__name__)
HistoryLoader = Callable[[str], tuple[pd.DataFrame, dict[str, Any]]]
PRICE_BASIS = "Yahoo Close; auto_adjust=False; cash distributions excluded"


def load_catalogue(path: Path) -> dict[str, Any]:
    """Read a reviewed catalogue and reject duplicate identities or symbols."""
    catalogue = json.loads(path.read_text())
    ids: set[str] = set()
    symbols: set[str] = set()
    for item in catalogue["instruments"]:
        if not item.get("id") or item["id"] in ids:
            raise ValueError("Catalogue IDs must be nonempty and unique")
        ids.add(item["id"])
        symbol = item.get("symbol")
        if symbol and symbol in symbols:
            raise ValueError(f"Duplicate Yahoo symbol: {symbol}")
        if symbol:
            symbols.add(symbol)
        if not item.get("name") or not item.get("category"):
            raise ValueError("Every investment needs a name and category")
        if not symbol and not item.get("mapping_note"):
            raise ValueError("Unmapped investments need an explanation")
    return catalogue


def fetch_history(symbol: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fetch ten years of daily closes and quote units without Finnhub calls."""
    ticker = yf.Ticker(symbol)
    frame = ticker.history(period="10y", interval="1d", auto_adjust=False,
                           actions=True, timeout=15)
    return frame, ticker.history_metadata


def serialise_history(frame: pd.DataFrame, metadata: dict[str, Any]) -> dict[str, Any]:
    """Keep local trading dates; convert pence to pounds, never invent FX rates."""
    currency = metadata.get("currency")
    if currency not in {"GBP", "GBp", "GBX", "USD", "EUR"}:
        raise ValueError(f"Missing or unsupported quote currency: {currency}")
    if frame.empty or "Close" not in frame or not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("No dated close-price history returned")
    factor = 0.01 if currency in {"GBp", "GBX"} else 1.0
    points: dict[str, float] = {}
    for timestamp, close in frame["Close"].items():
        value = float(close)
        if pd.notna(timestamp) and math.isfinite(value) and value > 0:
            # UTC conversion would move London summer midnight to the day before.
            points[timestamp.date().isoformat()] = round(value * factor, 8)
    if not points:
        raise ValueError("No finite positive close prices returned")
    adjusted = {}
    if "Adj Close" in frame:
        for timestamp, close in frame["Adj Close"].items():
            value = float(close)
            if pd.notna(timestamp) and math.isfinite(value) and value > 0:
                adjusted[timestamp.date().isoformat()] = round(value * factor, 8)
    return {"currency": "GBP" if factor == 0.01 else currency,
            "quote_currency": currency, "points": sorted(points.items()),
            "adjusted_points": sorted(adjusted.items())}


def build_snapshot(
    catalogue: dict[str, Any], *, loader: HistoryLoader = fetch_history,
    previous: dict[str, Any] | None = None, now: datetime | None = None,
) -> dict[str, Any]:
    """Isolate provider failures and retain explicitly stale last-good histories."""
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    old = {}
    if previous and previous.get("price_basis") == PRICE_BASIS:
        old = {item["id"]: item for item in previous.get("instruments", [])}
    instruments = []
    rate_limited = False
    for item in catalogue["instruments"]:
        result = dict(item)
        result.update(status="unavailable", points=[], adjusted_points=[], actions=[], action_fields=[], fetched_at=None)
        if not item.get("symbol"):
            result["error"] = item["mapping_note"]
        else:
            try:
                if rate_limited:
                    raise YFRateLimitError()
                frame, metadata = loader(item["symbol"])
                history = serialise_history(frame, metadata)
                actions = create_corporate_actions(
                    frame, symbol=item["symbol"], currency=metadata.get("currency")
                )
                result.update(history, status="ok", fetched_at=timestamp)
                result["action_fields"] = actions.attrs["available_fields"]
                result["actions"] = [{"date": index.date().isoformat(),
                    **{key: float(value) if pd.notna(value) else None
                       for key, value in row.items()}} for index, row in actions.iterrows()]
            except Exception as exc:
                rate_limited = rate_limited or isinstance(exc, YFRateLimitError)
                # Do not expose arbitrary provider responses in the public page.
                result["error"] = ("Yahoo Finance rate limited this refresh."
                                   if rate_limited else "Yahoo Finance history unavailable.")
                LOGGER.warning("%s: %s", item["symbol"], type(exc).__name__)
                cached = old.get(item["id"], {})
                if cached.get("symbol") == item["symbol"] and cached.get("points"):
                    for key in ("points", "adjusted_points", "currency", "quote_currency", "fetched_at", "actions", "action_fields"):
                        result[key] = cached.get(key)
                    result["status"] = "stale"
        instruments.append(result)
    return {"schema_version": 1, "generated_at": timestamp,
            "catalogue_checked_at": catalogue["checked_at"],
            "price_basis": PRICE_BASIS, "sources": catalogue["sources"],
            "instruments": instruments}


def write_site(snapshot: dict[str, Any], assets: Path, output: Path) -> None:
    """Build a self-contained static directory; refuse a wholly empty release."""
    if not any(item.get("points") for item in snapshot["instruments"]):
        raise ValueError("No price history available; refusing to replace the dashboard")
    output.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "styles.css", "app.mjs", "comparison.mjs"):
        shutil.copy2(assets / name, output / name)
    (output / ".nojekyll").touch()
    encoded = json.dumps(snapshot, allow_nan=False, separators=(",", ":"))
    temporary = output / "prices.json.tmp"
    temporary.write_text(encoded)
    temporary.replace(output / "prices.json")
    # Separate downloadable histories retain original quote units for cash
    # amounts. Parquet plus sidecar metadata is also reusable by modelling code.
    storage = ParquetStorage(output / "datasets")
    all_events = []
    for item in snapshot["instruments"]:
        if not item.get("points"):
            continue
        records = item.get("actions") or []
        frame = pd.DataFrame(records, columns=["date", "dividends", "capital_gains", "stock_splits"])
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.pop("date"), utc=True), name="date")
        frame.attrs = {"symbol": item["symbol"], "currency": item["quote_currency"],
                       "available_fields": item.get("action_fields") or [],
                       "fetched_at": item["fetched_at"], "status": item["status"],
                       "date_semantics": "exchange-local event/ex-date",
                       "value_basis": "Yahoo-reported per-share amounts; may be split-adjusted"}
        storage.save_dataset(frame, source="yfinance", dataset="corporate_actions")
        all_events.extend({"symbol": item["symbol"], "currency": item["quote_currency"],
                           "status": item["status"], "fetched_at": item["fetched_at"], **event}
                          for event in records)
    (output / "corporate-actions.json").write_text(json.dumps(
        {"generated_at": snapshot["generated_at"], "events": all_events,
         "availability": [{"symbol": i.get("symbol"), "fields": i.get("action_fields"),
                           "status": i["status"]} for i in snapshot["instruments"]]}, allow_nan=False))
    pd.DataFrame(all_events, columns=["symbol", "currency", "status", "fetched_at", "date",
                                     "dividends", "capital_gains", "stock_splits"]).to_csv(
                                         output / "corporate-actions.csv", index=False)


def main(argv: list[str] | None = None) -> None:
    """Build static assets and the current yfinance snapshot from the repository."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, default=Path("config/dodl-instruments.json"))
    parser.add_argument("--assets", type=Path, default=Path("dashboard"))
    parser.add_argument("--output", type=Path, default=Path("dashboard-dist"))
    parser.add_argument("--previous", type=Path, help="Optional last-good prices.json")
    args = parser.parse_args(argv)
    previous = None
    if args.previous and args.previous.exists():
        previous = json.loads(args.previous.read_text())
    catalogue = load_catalogue(args.catalogue)
    snapshot = build_snapshot(catalogue, previous=previous)
    # Keep a diagnostics file even if all data failed and publication is refused.
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "refresh-status.json").write_text(json.dumps(
        {"generated_at": snapshot["generated_at"], "instruments": [
            {key: row.get(key) for key in ("id", "symbol", "status", "error")}
            for row in snapshot["instruments"]]}, indent=2))
    write_site(snapshot, args.assets, args.output)
    available = sum(bool(row["points"]) for row in snapshot["instruments"])
    print(f"Published histories for {available}/{len(snapshot['instruments'])} investments")


def build_dashboard_series(
    market_data: pd.DataFrame,
    distributions: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Serialize one instrument's price and total-return history for the web UI."""

    history = build_return_history(market_data, distributions)
    records: list[dict[str, Any]] = []
    for timestamp, row in history.iterrows():
        records.append(
            {
                "date": pd.Timestamp(timestamp).date().isoformat(),
                "price": float(row["price"]),
                "distribution": float(row["cash_distribution"]),
                "price_index": float(row["price_index"]),
                "total_return_index": float(row["total_return_index"]),
            }
        )
    return records


def build_dashboard_payload(
    instruments: list[dict[str, Any]],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Wrap serialized instrument records with stable dashboard metadata."""

    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)

    return {
        "generated_at": timestamp.isoformat(),
        "instruments": instruments,
    }


if __name__ == "__main__":
    main()
