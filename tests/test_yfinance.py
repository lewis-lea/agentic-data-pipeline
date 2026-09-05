"""Tests for yfinance historical market-data ingestion."""

import pandas as pd
import pytest

from agentic_data_pipeline.ingestion import YFinanceClient, YFinanceError


def test_get_history_normalizes_dataframe() -> None:
    captured: dict[str, object] = {}

    def history_loader(symbol: str, **kwargs: object) -> pd.DataFrame:
        captured.update(symbol=symbol, **kwargs)
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1000, 1100],
            },
            index=pd.DatetimeIndex(["2026-01-02", "2026-01-05"], name="Date"),
        )

    frame = YFinanceClient(history_loader=history_loader).get_history(
        " aapl ", period="6mo", interval="1d"
    )

    assert isinstance(frame, pd.DataFrame)
    assert frame.attrs["symbol"] == "AAPL"
    assert frame.attrs["interval"] == "1d"
    assert list(frame.columns) == ["open", "high", "low", "close", "volume", "source"]
    assert len(frame) == 2
    assert frame.iloc[0]["source"] == "yfinance"
    assert frame.iloc[1]["close"] == 102.0
    assert str(frame.index.tz) == "UTC"
    assert captured == {
        "symbol": "AAPL",
        "interval": "1d",
        "auto_adjust": False,
        "actions": False,
        "period": "6mo",
    }


def test_get_history_prefers_explicit_date_range() -> None:
    captured: dict[str, object] = {}

    def history_loader(symbol: str, **kwargs: object) -> pd.DataFrame:
        captured.update(symbol=symbol, **kwargs)
        return pd.DataFrame(
            {"Open": [100.0], "High": [102.0], "Low": [99.0], "Close": [101.0], "Volume": [1000]},
            index=pd.DatetimeIndex(["2026-01-02"], name="Date"),
        )

    YFinanceClient(history_loader=history_loader).get_history(
        "AAPL", period="1y", start="2026-01-01", end="2026-02-01"
    )

    assert "period" not in captured
    assert captured["start"] == "2026-01-01"
    assert captured["end"] == "2026-02-01"


def test_get_history_rejects_empty_result() -> None:
    client = YFinanceClient(history_loader=lambda _symbol, **_kwargs: pd.DataFrame())

    with pytest.raises(YFinanceError, match="No historical data"):
        client.get_history("AAPL")


def test_get_history_rejects_empty_symbol() -> None:
    client = YFinanceClient(history_loader=lambda _symbol, **_kwargs: pd.DataFrame())

    with pytest.raises(ValueError, match="symbol must not be empty"):
        client.get_history("   ")


def test_get_distributions_normalizes_series_and_omits_zero_payments() -> None:
    captured: dict[str, object] = {}

    def distribution_loader(symbol: str, **kwargs: object) -> pd.Series:
        captured.update(symbol=symbol, **kwargs)
        return pd.Series(
            [0.0, 0.25, 0.3],
            index=pd.DatetimeIndex(
                ["2025-12-01", "2026-01-15", "2026-04-15"],
                tz="Europe/London",
                name="Date",
            ),
            name="Dividends",
        )

    frame = YFinanceClient(distribution_loader=distribution_loader).get_distributions(
        " vhyl.l ", start="2026-01-01", end="2026-06-01"
    )

    assert captured == {
        "symbol": "VHYL.L",
        "start": "2026-01-01",
        "end": "2026-06-01",
    }
    assert list(frame.columns) == ["cash_amount", "source"]
    assert frame["cash_amount"].tolist() == [0.25, 0.3]
    assert frame["source"].tolist() == ["yfinance", "yfinance"]
    assert str(frame.index.tz) == "UTC"
    assert frame.index.name == "timestamp"
    assert frame.attrs["symbol"] == "VHYL.L"
    assert frame.attrs["dataset"] == "distributions"


def test_get_distributions_accepts_dividends_dataframe_and_empty_result() -> None:
    index = pd.DatetimeIndex(["2026-01-15"], tz="UTC")
    dataframe_client = YFinanceClient(
        distribution_loader=lambda _symbol, **_kwargs: pd.DataFrame(
            {"Dividends": [0.2]}, index=index
        )
    )
    assert dataframe_client.get_distributions("ABC").iloc[0]["cash_amount"] == 0.2

    empty_client = YFinanceClient(
        distribution_loader=lambda _symbol, **_kwargs: pd.Series(
            dtype=float, index=pd.DatetimeIndex([], tz="UTC")
        )
    )
    empty = empty_client.get_distributions("ABC")
    assert empty.empty
    assert list(empty.columns) == ["cash_amount", "source"]


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (["not", "pandas"], "Series or DataFrame"),
        (
            pd.Series([1.0], index=pd.Index(["not-a-date"])),
            "DatetimeIndex",
        ),
        (
            pd.Series(["bad"], index=pd.DatetimeIndex(["2026-01-01"])),
            "non-numeric",
        ),
        (
            pd.Series([-1.0], index=pd.DatetimeIndex(["2026-01-01"])),
            "must not be negative",
        ),
        (
            pd.DataFrame(
                {"Other": [1.0]}, index=pd.DatetimeIndex(["2026-01-01"])
            ),
            "must contain Dividends",
        ),
    ],
)
def test_get_distributions_rejects_invalid_responses(raw: object, message: str) -> None:
    client = YFinanceClient(distribution_loader=lambda _symbol, **_kwargs: raw)  # type: ignore[arg-type]
    with pytest.raises(YFinanceError, match=message):
        client.get_distributions("ABC")


def test_get_distributions_wraps_provider_errors() -> None:
    def broken(_symbol: str, **_kwargs: object) -> pd.Series:
        raise RuntimeError("boom")

    with pytest.raises(YFinanceError, match="Could not retrieve distributions"):
        YFinanceClient(distribution_loader=broken).get_distributions("ABC")


@pytest.mark.parametrize('explicit_range', [False, True])
def test_default_distribution_loader_requests_unadjusted_actions(monkeypatch, explicit_range):
    captured = {}
    class Ticker:
        def history(self, **kwargs):
            captured.update(kwargs)
            return pd.DataFrame({'Dividends': [0.25]}, index=pd.DatetimeIndex(['2026-01-15']))
    monkeypatch.setattr('agentic_data_pipeline.ingestion.yfinance.yf.Ticker', lambda _: Ticker())
    kwargs = {'start': '2026-01-01', 'end': '2026-02-01'} if explicit_range else {}
    result = YFinanceClient().get_distributions('AAPL', **kwargs)
    assert result.cash_amount.tolist() == [0.25]
    assert captured == {'actions': True, 'auto_adjust': False, **(kwargs or {'period': 'max'})}


@pytest.mark.parametrize('frame', [pd.DataFrame(), pd.DataFrame({'Close': [100]}, index=pd.DatetimeIndex(['2026-01-15']))])
def test_default_distribution_loader_does_not_report_failed_history_as_no_dividends(monkeypatch, frame):
    class Ticker:
        def history(self, **kwargs):
            return frame
    monkeypatch.setattr('agentic_data_pipeline.ingestion.yfinance.yf.Ticker', lambda _: Ticker())
    with pytest.raises(YFinanceError, match='availability is unknown'):
        YFinanceClient().get_distributions('AAPL')
