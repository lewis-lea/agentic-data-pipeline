"""Build the static investment-return dashboard from the current Dodl range."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

import yfinance as yf

from agentic_data_pipeline.dashboard import build_dashboard_payload, build_dashboard_series
from agentic_data_pipeline.ingestion import YFinanceClient

DODL_SOURCES = {
    "share": "https://dodl.co.uk/investments/shares",
    "themed": "https://dodl.co.uk/investments/themed",
    "fund": "https://dodl.co.uk/investments/funds",
}
USER_AGENT = "agentic-data-pipeline-dashboard/1.0"


@dataclass(frozen=True)
class Candidate:
    name: str
    category: str


class _BlockParser(HTMLParser):
    """Collect heading/paragraph text blocks without a third-party HTML parser."""

    BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "p", "li"}

    def __init__(self) -> None:
        super().__init__()
        self._active: str | None = None
        self._parts: list[str] = []
        self.blocks: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.BLOCK_TAGS:
            self._flush()
            self._active = tag

    def handle_endtag(self, tag: str) -> None:
        if self._active == tag:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._active:
            self._parts.append(data)

    def _flush(self) -> None:
        if self._active:
            text = " ".join("".join(self._parts).split())
            if text:
                self.blocks.append((self._active, text))
        self._active = None
        self._parts = []


def fetch_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_candidates(html: str, category: str) -> list[Candidate]:
    parser = _BlockParser()
    parser.feed(html)
    blocks = parser.blocks
    names: list[str] = []

    if category == "share":
        ignored = {
            "About this company",
            "What else do you need to know?",
            "Browse the shares",
        }
        for tag, text in blocks:
            if tag == "h4" and text not in ignored and not text.startswith("What "):
                names.append(text)
    else:
        for index, (_tag, text) in enumerate(blocks):
            if text.casefold() == "what's the fund?":
                for _, following in blocks[index + 1 : index + 5]:
                    if following and not following.startswith("What's "):
                        names.append(following)
                        break

    unique: dict[str, Candidate] = {}
    for name in names:
        clean = re.sub(r"\s+", " ", name).strip()
        if clean:
            unique[clean.casefold()] = Candidate(clean, category)
    return list(unique.values())


def discover_dodl_candidates() -> list[Candidate]:
    found: dict[tuple[str, str], Candidate] = {}
    for category, url in DODL_SOURCES.items():
        html = fetch_html(url)
        for candidate in extract_candidates(html, category):
            found[(candidate.category, candidate.name.casefold())] = candidate
    return sorted(found.values(), key=lambda item: (item.category, item.name.casefold()))


def _normalise_name(value: str) -> set[str]:
    return {
        token
        for token in re.sub(r"[^a-z0-9]+", " ", value.casefold()).split()
        if len(token) > 1
    }


def resolve_symbol(candidate: Candidate) -> str | None:
    quotes = yf.Search(candidate.name, max_results=10).quotes
    wanted = _normalise_name(candidate.name)
    best: tuple[float, str] | None = None

    for quote in quotes:
        symbol = str(quote.get("symbol") or "").strip()
        if not symbol:
            continue
        quote_type = str(quote.get("quoteType") or "").upper()
        if candidate.category == "share" and quote_type != "EQUITY":
            continue
        if candidate.category != "share" and quote_type not in {
            "ETF",
            "MUTUALFUND",
            "EQUITY",
        }:
            continue

        names = " ".join(
            str(quote.get(key) or "")
            for key in ("shortname", "longname", "displayName")
        )
        actual = _normalise_name(names)
        overlap = len(wanted & actual) / max(len(wanted), 1)
        score = overlap * 100
        if symbol.endswith(".L"):
            score += 12 if candidate.category != "share" else 6
        if quote_type in {"ETF", "MUTUALFUND"} and candidate.category != "share":
            score += 10
        if quote_type == "EQUITY" and candidate.category == "share":
            score += 10

        if best is None or score > best[0]:
            best = (score, symbol)

    return best[1] if best and best[0] >= 35 else None


def build_instrument(
    candidate: Candidate,
    client: YFinanceClient,
    *,
    period: str,
) -> dict[str, object] | None:
    symbol = resolve_symbol(candidate)
    if symbol is None:
        return None

    history = client.get_history(symbol, period=period, interval="1d", auto_adjust=False)
    distributions = client.get_distributions(symbol, start=history.index.min())
    return {
        "symbol": symbol,
        "name": candidate.name,
        "category": candidate.category,
        "series": build_dashboard_series(history, distributions),
    }


def write_site(output: Path, *, period: str, throttle: float) -> None:
    output.mkdir(parents=True, exist_ok=True)
    template_root = Path(__file__).resolve().parents[1] / "dashboard"
    for filename in ("index.html", "app.js", "styles.css"):
        shutil.copy2(template_root / filename, output / filename)

    client = YFinanceClient()
    instruments: list[dict[str, object]] = []
    unresolved: list[dict[str, str]] = []

    for candidate in discover_dodl_candidates():
        try:
            instrument = build_instrument(candidate, client, period=period)
        except Exception as exc:  # one bad instrument should not break the whole site
            print(f"warning: {candidate.name}: {exc}", file=sys.stderr)
            instrument = None
        if instrument is None:
            unresolved.append({"name": candidate.name, "category": candidate.category})
        else:
            instruments.append(instrument)
        if throttle:
            time.sleep(throttle)

    if not instruments:
        raise RuntimeError("No Dodl instruments could be resolved to yfinance data")

    payload = build_dashboard_payload(instruments)
    payload["source"] = {
        "provider": "yfinance",
        "universe": "AJ Bell Dodl public investment range",
        "urls": DODL_SOURCES,
        "period": period,
        "resolved_count": len(instruments),
        "unresolved": unresolved,
    }
    data_dir = output / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "market.json").write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("site"))
    parser.add_argument("--period", default="5y")
    parser.add_argument("--throttle", type=float, default=0.05)
    args = parser.parse_args(list(argv) if argv is not None else None)
    write_site(args.output, period=args.period, throttle=args.throttle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
