"""Offline regression checks for published histories and distributions."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
from yfinance.exceptions import YFRateLimitError

from agentic_data_pipeline import dashboard
from agentic_data_pipeline.corporate_actions import create_corporate_actions
from agentic_data_pipeline.ingestion import YFinanceClient, YFinanceError
from agentic_data_pipeline.storage import ParquetStorage

NOW = datetime(2026, 9, 4, tzinfo=timezone.utc)


@pytest.fixture
def history():
    return pd.DataFrame({"Close": [1000., 1100.], "Adj Close": [900., 1000.],
                         "Dividends": [0., 15.], "Stock Splits": [0., 2.],
                         "Capital Gains": [0., 5.]},
                        index=pd.date_range("2026-08-03", periods=2, tz="Europe/London"))


@pytest.fixture
def catalogue():
    return {"checked_at": "2026-09-04", "sources": [], "instruments": [
        {"id": "a", "name": "A", "category": "Shares", "symbol": "A.L"},
        {"id": "b", "name": "B", "category": "Funds", "symbol": None,
         "mapping_note": "Unknown share class"}]}


def test_snapshot_preserves_local_dates_pence_and_separate_adjusted_prices(history, catalogue):
    result = dashboard.build_snapshot(catalogue, loader=lambda _: (history, {"currency": "GBp"}), now=NOW)
    a, b = result["instruments"]
    assert a["points"] == [("2026-08-03", 10.), ("2026-08-04", 11.)]
    assert a["adjusted_points"] == [("2026-08-03", 9.), ("2026-08-04", 10.)]
    assert a["currency"] == "GBP" and a["quote_currency"] == "GBp"
    assert a["actions"] == [{"date": "2026-08-04", "dividends": 15., "capital_gains": 5., "stock_splits": 2.}]
    assert a["status"] == "ok" and a["fetched_at"] == NOW.isoformat()
    assert b["status"] == "unavailable" and b["error"] == "Unknown share class"


@pytest.mark.parametrize("currency", ["GBP", "USD", "EUR", "GBX"])
def test_quote_currencies_are_explicit(history, currency):
    result = dashboard.serialise_history(history, {"currency": currency})
    assert result["points"][0][1] == (10 if currency == "GBX" else 1000)


@pytest.mark.parametrize("currency", [None, "XYZ"])
def test_unknown_currency_is_not_guessed(history, currency):
    with pytest.raises(ValueError, match="currency"):
        dashboard.serialise_history(history, {"currency": currency})


def test_history_rejects_invalid_frames_and_filters_bad_prices(history):
    for frame in [pd.DataFrame(), pd.DataFrame({"Close": [1]}), history.drop(columns="Close")]:
        with pytest.raises(ValueError, match="dated close"):
            dashboard.serialise_history(frame, {"currency": "GBP"})
    history.loc[history.index[0], ["Close", "Adj Close"]] = float("nan")
    assert len(dashboard.serialise_history(history, {"currency": "GBP"})["points"]) == 1
    history["Close"] = 0
    with pytest.raises(ValueError, match="finite positive"):
        dashboard.serialise_history(history, {"currency": "GBP"})


def test_missing_adjustments_are_not_replaced_with_prices(history):
    result = dashboard.serialise_history(history.drop(columns="Adj Close"), {"currency": "GBP"})
    assert result["adjusted_points"] == []


def test_provider_failure_retains_stale_snapshot_and_rate_limit_stops_requests(history, catalogue):
    first = dashboard.build_snapshot(catalogue, loader=lambda _: (history, {"currency": "USD"}), now=NOW)
    catalogue["instruments"].append({"id": "c", "name": "C", "category": "Shares", "symbol": "C"})
    loader = Mock(side_effect=YFRateLimitError())
    result = dashboard.build_snapshot(catalogue, loader=loader, previous=first)
    loader.assert_called_once_with("A.L")
    assert result["instruments"][0]["status"] == "stale"
    assert result["instruments"][0]["actions"] == first["instruments"][0]["actions"]
    assert result["instruments"][0]["fetched_at"] == first["instruments"][0]["fetched_at"]
    assert result["instruments"][2]["status"] == "unavailable"


def test_cache_is_never_reused_for_a_different_symbol_or_price_basis(history, catalogue):
    old = dashboard.build_snapshot(catalogue, loader=lambda _: (history, {"currency": "USD"}))
    loader = Mock(side_effect=RuntimeError("secret provider response"))
    for change in ["symbol", "price_basis"]:
        previous = json.loads(json.dumps(old))
        if change == "symbol":
            previous["instruments"][0]["symbol"] = "OTHER"
        else:
            previous["price_basis"] = "different"
        result = dashboard.build_snapshot(catalogue, loader=loader, previous=previous)
        assert result["instruments"][0]["points"] == []
        assert "secret" not in json.dumps(result)


def test_invalid_actions_do_not_publish_partially_valid_price_data(history, catalogue):
    history["Dividends"] = -1
    result = dashboard.build_snapshot(catalogue, loader=lambda _: (history, {"currency": "GBP"}))
    assert result["instruments"][0]["status"] == "unavailable"
    assert result["instruments"][0]["points"] == []


def test_site_build_writes_downloadable_action_datasets_and_keeps_all_instruments(tmp_path, history, catalogue):
    snapshot = dashboard.build_snapshot(catalogue, loader=lambda _: (history, {"currency": "GBp"}), now=NOW)
    assets = Path(__file__).parents[1] / "dashboard"
    dashboard.write_site(snapshot, assets, tmp_path)
    result = json.loads((tmp_path / "prices.json").read_text())
    assert len(result["instruments"]) == 2
    for path in ["index.html", "app.mjs", "styles.css", "comparison.mjs", ".nojekyll", "corporate-actions.csv", "corporate-actions.json"]:
        assert (tmp_path / path).is_file()
    saved = ParquetStorage(tmp_path / "datasets").load_dataset(source="yfinance", dataset="corporate_actions", symbol="A.L")
    assert saved["dividends"].iloc[0] == 15
    assert saved.attrs["currency"] == "GBp"
    assert saved.index[0] == pd.Timestamp("2026-08-04", tz="UTC")
    assert pd.read_csv(tmp_path / "corporate-actions.csv")["stock_splits"].iloc[0] == 2


def test_empty_build_does_not_replace_existing_site(tmp_path):
    (tmp_path / "prices.json").write_text("previous")
    with pytest.raises(ValueError, match="refusing"):
        dashboard.write_site({"instruments": []}, tmp_path, tmp_path)
    assert (tmp_path / "prices.json").read_text() == "previous"


def test_yfinance_fetch_requests_actions_without_price_auto_adjustment(monkeypatch, history):
    ticker = Mock(history_metadata={"currency": "GBP"})
    ticker.history.return_value = history
    factory = Mock(return_value=ticker)
    monkeypatch.setattr(dashboard.yf, "Ticker", factory)
    frame, metadata = dashboard.fetch_history("A.L")
    assert frame is history and metadata["currency"] == "GBP"
    assert ticker.history.call_args.kwargs["actions"] is True
    assert ticker.history.call_args.kwargs["auto_adjust"] is False


def test_catalogue_validation_and_reviewed_universe(tmp_path, catalogue):
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(catalogue))
    assert dashboard.load_catalogue(path) == catalogue
    for change in ["duplicate", "empty_id", "symbol", "name", "category", "note"]:
        bad = json.loads(json.dumps(catalogue))
        if change == "duplicate": bad["instruments"][1]["id"] = "a"
        if change == "empty_id": bad["instruments"][0]["id"] = ""
        if change == "symbol": bad["instruments"][1]["symbol"] = "A.L"
        if change in {"name", "category"}: bad["instruments"][0][change] = ""
        if change == "note": del bad["instruments"][1]["mapping_note"]
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError): dashboard.load_catalogue(path)
    actual = dashboard.load_catalogue(Path(__file__).parents[1] / "config/dodl-instruments.json")
    assert len(actual["instruments"]) == 94
    assert len([i for i in actual["instruments"] if i["category"] == "Shares"]) == 58
    assert len([i for i in actual["instruments"] if i["category"] == "Bond funds"]) == 4
    assert not {"NFLX", "COST", "DIS"} & {i["symbol"] for i in actual["instruments"]}


def test_cli_writes_site_and_loads_optional_previous_snapshot(monkeypatch, tmp_path, catalogue, history):
    path = tmp_path / "catalogue.json"; path.write_text(json.dumps(catalogue))
    snapshot = dashboard.build_snapshot(catalogue, loader=lambda _: (history, {"currency": "USD"}))
    build = Mock(return_value=snapshot); monkeypatch.setattr(dashboard, "build_snapshot", build)
    for exists in [False, True]:
        previous = tmp_path / "previous.json"
        if exists: previous.write_text(json.dumps(snapshot))
        dashboard.main(["--catalogue", str(path), "--output", str(tmp_path / "dist"), "--previous", str(previous)])
        assert build.call_args.kwargs["previous"] == (json.loads(previous.read_text()) if exists else None)
    assert (tmp_path / "dist/refresh-status.json").exists()


def test_actions_normalise_events_and_persist_missing_fields_as_unknown(history):
    history = history.drop(columns="Capital Gains")
    result = create_corporate_actions(history, symbol=" a.l ", currency="GBp")
    assert len(result) == 1 and result.attrs["symbol"] == "A.L"
    assert result.iloc[0]["dividends"] == 15
    assert pd.isna(result.iloc[0]["capital_gains"])
    assert "capital_gains" not in result.attrs["available_fields"]
    assert str(result.index.tz) == "UTC" and result.index[0].day == 4


def test_actions_distinguish_no_events_from_missing_provider_fields(history):
    zeros = history.copy(); zeros[["Dividends", "Stock Splits", "Capital Gains"]] = 0
    known = create_corporate_actions(zeros, symbol="A")
    unknown = create_corporate_actions(history[["Close"]], symbol="A")
    assert known.empty and unknown.empty
    assert len(known.attrs["available_fields"]) == 3
    assert unknown.attrs["available_fields"] == []


def test_actions_validate_inputs_and_deduplicate_dates(history):
    for frame in [None, pd.DataFrame({"Dividends": [1]})]:
        with pytest.raises(ValueError): create_corporate_actions(frame, symbol="A")
    with pytest.raises(ValueError): create_corporate_actions(history, symbol=" ")
    for value in [-1, float("inf")]:
        bad = history.copy(); bad["Dividends"] = value
        with pytest.raises(ValueError, match="non-negative"): create_corporate_actions(bad, symbol="A")
    bad = history.iloc[[1]].copy(); bad.index = pd.DatetimeIndex([pd.NaT])
    with pytest.raises(ValueError, match="dates"): create_corporate_actions(bad, symbol="A")
    assert len(create_corporate_actions(pd.concat([history, history]), symbol="A")) == 1


def test_client_actions_are_historical_and_use_the_existing_storage_contract(history, tmp_path):
    history.attrs["currency"] = "GBp"
    loader = Mock(return_value=history)
    client = YFinanceClient(history_loader=loader)
    actions = client.get_actions(" a.l ")
    loader.assert_called_once_with("A.L", interval="1d", auto_adjust=False, actions=True, period="max")
    path = ParquetStorage(tmp_path).save_dataset(actions, source="yfinance", dataset="corporate_actions")
    assert path == tmp_path / "raw/yfinance/corporate_actions/A.L.parquet"
    assert actions.attrs["currency"] == "GBp"
    client.get_actions("A.L", start="2020-01-01", end="2026-01-01")
    assert "period" not in loader.call_args.kwargs
    assert loader.call_args.kwargs["end"] == "2026-01-01"


def test_client_actions_handle_provider_failures_and_empty_histories():
    for response in [pd.DataFrame(), None]:
        with pytest.raises(YFinanceError, match="availability is unknown"):
            YFinanceClient(history_loader=lambda *_a, **_k: response).get_actions("A")
    with pytest.raises(YFinanceError): YFinanceClient(history_loader=Mock(side_effect=OSError())).get_actions("A")
    with pytest.raises(ValueError): YFinanceClient().get_actions(" ")


def test_default_client_actions_loader_attaches_quote_currency(monkeypatch, history):
    ticker = Mock(history_metadata={"currency": "GBp"}); ticker.history.return_value = history
    monkeypatch.setattr(dashboard.yf, "Ticker", Mock(return_value=ticker))
    assert YFinanceClient().get_actions("A.L").attrs["currency"] == "GBp"
