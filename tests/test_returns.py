"""Tests for explicit cash-distribution return calculations."""

import pandas as pd
import pytest

from agentic_data_pipeline.returns import build_return_history


def market_frame(prices: list[float]) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=len(prices), freq="D", tz="UTC", name="timestamp")
    frame = pd.DataFrame({"close": prices}, index=index)
    frame.attrs["symbol"] = "TEST"
    return frame


def test_total_return_reinvests_cash_distribution() -> None:
    market = market_frame([100.0, 90.0, 99.0])
    distributions = pd.DataFrame(
        {"cash_amount": [10.0]},
        index=pd.DatetimeIndex(["2026-01-02"], tz="UTC", name="timestamp"),
    )

    result = build_return_history(market, distributions)

    assert result["price_index"].tolist() == pytest.approx([100.0, 90.0, 99.0])
    assert result["cash_distribution"].tolist() == pytest.approx([0.0, 10.0, 0.0])
    assert result["total_return_index"].tolist() == pytest.approx([100.0, 100.0, 110.0])
    assert result.attrs["symbol"] == "TEST"
    assert result.attrs["return_base"] == 100.0


def test_distribution_between_bars_aligns_to_next_market_observation() -> None:
    market = market_frame([100.0, 100.0])
    distributions = pd.DataFrame(
        {"cash_amount": [5.0]},
        index=pd.DatetimeIndex(["2026-01-01 12:00"], tz="UTC"),
    )

    result = build_return_history(market, distributions)
    assert result["cash_distribution"].tolist() == [0.0, 5.0]
    assert result["total_return_index"].iloc[-1] == pytest.approx(105.0)


def test_multiple_distributions_at_same_timestamp_are_summed() -> None:
    market = market_frame([100.0, 100.0])
    timestamp = pd.Timestamp("2026-01-02", tz="UTC")
    distributions = pd.DataFrame(
        {"cash_amount": [2.0, 3.0]},
        index=pd.DatetimeIndex([timestamp, timestamp]),
    )

    result = build_return_history(market, distributions)
    assert result["cash_distribution"].iloc[-1] == pytest.approx(5.0)


def test_distribution_after_market_range_is_ignored() -> None:
    market = market_frame([100.0, 101.0])
    distributions = pd.DataFrame(
        {"cash_amount": [10.0]},
        index=pd.DatetimeIndex(["2027-01-01"], tz="UTC"),
    )
    result = build_return_history(market, distributions)
    assert result["cash_distribution"].sum() == 0.0


def test_custom_base_and_no_distributions() -> None:
    result = build_return_history(market_frame([50.0, 55.0]), base=1.0)
    assert result["price_index"].tolist() == pytest.approx([1.0, 1.1])
    assert result["total_return_index"].tolist() == pytest.approx([1.0, 1.1])


@pytest.mark.parametrize(
    ("market", "message"),
    [
        ("bad", "DataFrame"),
        (pd.DataFrame({"close": [1.0]}), "DatetimeIndex"),
        (
            pd.DataFrame(
                {"open": [1.0]},
                index=pd.DatetimeIndex(["2026-01-01"]),
            ),
            "close column",
        ),
        (
            pd.DataFrame(
                {"close": []},
                index=pd.DatetimeIndex([]),
            ),
            "at least one",
        ),
        (market_frame([0.0]), "positive and finite"),
    ],
)
def test_invalid_market_data_is_rejected(market: object, message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        build_return_history(market)  # type: ignore[arg-type]


@pytest.mark.parametrize("base", [0.0, -1.0, float("inf")])
def test_invalid_base_is_rejected(base: float) -> None:
    with pytest.raises(ValueError, match="base"):
        build_return_history(market_frame([100.0]), base=base)


def test_invalid_distribution_data_is_rejected() -> None:
    market = market_frame([100.0, 100.0])

    with pytest.raises(TypeError, match="DataFrame"):
        build_return_history(market, "bad")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="DatetimeIndex"):
        build_return_history(market, pd.DataFrame({"cash_amount": [1.0]}))

    missing = pd.DataFrame(
        {"other": [1.0]}, index=pd.DatetimeIndex(["2026-01-01"])
    )
    with pytest.raises(ValueError, match="cash_amount"):
        build_return_history(market, missing)

    negative = pd.DataFrame(
        {"cash_amount": [-1.0]},
        index=pd.DatetimeIndex(["2026-01-01"], tz="UTC"),
    )
    with pytest.raises(ValueError, match="non-negative"):
        build_return_history(market, negative)
