from datetime import date, datetime

from trading_agent.core.equity import V3_STEP5_PORTFOLIO_CONFIG
from trading_agent.core.market import MarketData
from trading_agent.data.index import load_nifty50_price_history
from trading_agent.research.relative_strength import (
    REGIME_SMA_PERIOD, evaluate_relative_strength, regime_risk_on,
)


def business_days(start, count):
    result = []
    day = start
    from datetime import timedelta
    while len(result) < count:
        if day.weekday() < 5:
            result.append(day)
        day += timedelta(days=1)
    return result


def history(symbol, slope=.2, count=900, remove=None):
    remove = set(remove or ())
    rows = []
    for index, day in enumerate(business_days(date(2018, 1, 1), count)):
        if day in remove:
            continue
        close = 100 + slope * index
        rows.append(MarketData(
            date=datetime.combine(day, datetime.min.time()), symbol=symbol,
            open=close - .1, high=close + 1, low=close - 1, close=close,
            volume=500_000,
        ))
    return rows


def regime(overrides=None, count=900, remove=None):
    overrides = overrides or {}
    remove = set(remove or ())
    rows = []
    for day in business_days(date(2018, 1, 1), count):
        if day in remove:
            continue
        close = overrides.get(day, 100.0)
        rows.append(MarketData(
            date=datetime.combine(day, datetime.min.time()), symbol="NIFTY 50",
            open=close, high=close + 1, low=close - 1, close=close, volume=None,
        ))
    return rows


def run(data, regime_rows, end=date(2020, 5, 29)):
    return evaluate_relative_strength(
        data, V3_STEP5_PORTFOLIO_CONFIG, development_start=date(2020, 1, 1),
        development_end=end, retrospective_static_membership=True,
        regime_history=regime_rows,
    )


def test_regime_requires_exactly_200_observations_and_strict_above():
    rows = regime(count=REGIME_SMA_PERIOD)
    assert regime_risk_on(rows[:-1], rows[-2].date.date()) == (
        False, "missing_date_or_history")
    assert regime_risk_on(rows, rows[-1].date.date()) == (False, "available")
    raised = list(rows)
    raised[-1] = raised[-1].model_copy(update={"close": 101})
    assert regime_risk_on(raised, raised[-1].date.date()) == (True, "available")


def test_missing_index_date_is_risk_off_without_forward_read():
    rows = regime(remove={date(2020, 1, 31)})
    assert regime_risk_on(rows, date(2020, 1, 31)) == (
        False, "missing_date_or_history")


def test_overlay_keeps_step1_rankings_but_blocks_entries_when_risk_off():
    data = {"A": history("A", .3)}
    all_off = regime()
    result = run(data, all_off)
    assert any(result.monthly_rankings.values())
    assert all(not selected for selected in result.monthly_selections.values())
    assert not any(item.startswith("BUY") for item in result.execution_log)


def test_risk_off_liquidates_next_open_and_later_risk_on_reenters():
    regime_rows = regime({
        date(2020, 1, 31): 200,
        date(2020, 2, 28): 50,
        date(2020, 3, 31): 200,
    })
    result = run({"A": history("A", .3)}, regime_rows)
    assert result.monthly_selections[date(2020, 1, 31)] == ("A",)
    assert result.monthly_selections[date(2020, 2, 28)] == ()
    assert result.monthly_selections[date(2020, 3, 31)] == ("A",)
    assert "BUY:A:2020-02-03" in result.execution_log
    assert "SELL:A:2020-03-02" in result.execution_log
    assert "BUY:A:2020-04-01" in result.execution_log


def test_risk_off_symbol_missing_next_open_defers_only_its_sale():
    regime_rows = regime({date(2020, 1, 31): 200, date(2020, 2, 28): 50})
    data = {
        "A": history("A", .3, remove={date(2020, 3, 2)}),
        "B": history("B", .2),
    }
    result = run(data, regime_rows)
    assert result.deferred_orders >= 1
    assert "SELL:B:2020-03-02" in result.execution_log
    assert "SELL:A:2020-03-03" in result.execution_log


def test_future_index_mutation_cannot_change_earlier_regime_or_trades():
    base_regime = regime({date(2020, 1, 31): 200})
    changed = [
        row.model_copy(update={"close": 1_000_000})
        if row.date.date() >= date(2020, 4, 1) else row
        for row in base_regime
    ]
    data = {"A": history("A", .3)}
    base = run(data, base_regime)
    future = run(data, changed)
    for day in base.monthly_selections:
        if day < date(2020, 4, 1):
            assert base.monthly_selections[day] == future.monthly_selections[day]


def test_stored_nifty_regime_history_is_unique_and_covers_development():
    from pathlib import Path
    rows = load_nifty50_price_history(Path(__file__).parents[1] / "data")
    days = [row.date.date() for row in rows]
    assert len(days) == len(set(days))
    assert days[0] == date(2020, 1, 1)
    assert date(2025, 8, 29) in days
