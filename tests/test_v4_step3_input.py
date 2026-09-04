from datetime import date, datetime, timedelta

import pytest

from trading_agent.core.market import MarketData
from trading_agent.core.universe import UniverseMember
from trading_agent.execution.v4_input import build_v4_decision_input
from trading_agent.research.relative_strength import (
    REGIME_SMA_PERIOD,
    rank_relative_strength,
)


SIGNAL = date(2026, 9, 30)
AS_OF = date(2026, 10, 2)


def sessions(ending, count):
    result = []
    day = ending
    while len(result) < count:
        if day.weekday() < 5:
            result.append(day)
        day -= timedelta(days=1)
    return list(reversed(result))


def rows(symbol, slope, *, future_open=200):
    values = []
    for index, day in enumerate(sessions(SIGNAL, 253)):
        close = 100 + slope * index
        values.append(MarketData(
            date=datetime.combine(day, datetime.min.time()), symbol=symbol,
            open=close, high=close + 1, low=close - 1, close=close,
            volume=200_000,
        ))
    values.append(MarketData(
        date=datetime(2026, 10, 1), symbol=symbol, open=future_open,
        high=future_open + 1, low=future_open - 1, close=future_open,
        volume=200_000,
    ))
    values.append(values[-1].model_copy(update={
        "date": datetime(2026, 10, 2), "open": 999,
    }))
    return values


def regime():
    return [MarketData(
        date=datetime.combine(day, datetime.min.time()), symbol="NIFTY 50",
        open=100 + index, high=101 + index, low=99 + index,
        close=100 + index, volume=None,
    ) for index, day in enumerate(sessions(SIGNAL, REGIME_SMA_PERIOD))]


def members(as_of=date(2026, 9, 4)):
    return [UniverseMember(as_of=as_of, index_name="NIFTY 50", symbol=symbol)
            for symbol in ("A", "B")]


def test_generator_matches_locked_ranking_and_regime_and_uses_first_next_open():
    histories = {"A": rows("A", .5, future_open=210), "B": rows("B", .2, future_open=110)}
    payload = build_v4_decision_input(
        histories, regime(), members(), signal_date=SIGNAL, as_of=AS_OF,
    )
    scores = {item["symbol"]: item["momentum"] for item in payload.candidates}
    assert tuple(item["symbol"] for item in payload.candidates) == rank_relative_strength(scores)
    assert payload.regime_close == regime()[-1].close
    assert payload.regime_sma200 == sum(row.close for row in regime()) / 200
    assert {item["symbol"]: item["open"] for item in payload.prices} == {"A": 210, "B": 110}
    assert payload.membership_snapshot_dates == (date(2026, 9, 4),)


def test_future_close_cannot_change_signal_or_ranking():
    base = {"A": rows("A", .5), "B": rows("B", .2)}
    changed = {symbol: list(history) for symbol, history in base.items()}
    changed["B"][-1] = changed["B"][-1].model_copy(update={"close": 1_000_000})
    first = build_v4_decision_input(base, regime(), members(), signal_date=SIGNAL, as_of=AS_OF)
    second = build_v4_decision_input(changed, regime(), members(), signal_date=SIGNAL, as_of=AS_OF)
    assert first.candidates == second.candidates


def test_generator_rejects_same_day_plan_and_unknown_membership():
    with pytest.raises(ValueError, match="later than signal_date"):
        build_v4_decision_input({}, regime(), members(), signal_date=SIGNAL, as_of=SIGNAL)
    with pytest.raises(ValueError, match="no universe snapshot"):
        build_v4_decision_input(
            {}, regime(), members(date(2026, 10, 1)), signal_date=SIGNAL, as_of=AS_OF,
        )


def test_generator_requires_exact_signal_date_for_regime():
    with pytest.raises(ValueError, match="no close on signal_date"):
        build_v4_decision_input(
            {}, regime()[:-1], members(), signal_date=SIGNAL, as_of=AS_OF,
        )
