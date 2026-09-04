from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from trading_agent.core.equity import V3_STEP5_PORTFOLIO_CONFIG
from trading_agent.core.market import MarketData
from trading_agent.core.universe import UniverseMember
from trading_agent.research.relative_strength import (
    MOMENTUM_LOOKBACK, MOMENTUM_SKIP, evaluate_relative_strength,
    momentum_score, rank_relative_strength,
)


def business_days(start, count):
    result = []
    day = start
    while len(result) < count:
        if day.weekday() < 5:
            result.append(day)
        day += timedelta(days=1)
    return result


def history(symbol, slope=0.2, count=900, remove=None, future_delta=0):
    rows = []
    remove = set(remove or ())
    for index, day in enumerate(business_days(date(2018, 1, 1), count)):
        if day in remove:
            continue
        close = 100 + slope * index
        if day >= date(2025, 9, 1):
            close += future_delta
        rows.append(MarketData(
            date=datetime.combine(day, datetime.min.time()), symbol=symbol,
            open=close - .1, high=close + 1, low=close - 1, close=close,
            volume=500_000,
        ))
    return rows


def run(data, start=date(2020, 1, 1), end=date(2020, 6, 30), **kwargs):
    return evaluate_relative_strength(
        data, V3_STEP5_PORTFOLIO_CONFIG, development_start=start,
        development_end=end, retrospective_static_membership=True, **kwargs,
    )


def test_12_minus_1_uses_exact_252_and_21_observations():
    rows = history("A", count=300)
    assert momentum_score(rows, 251) is None
    expected = rows[252 - MOMENTUM_SKIP].close / rows[252 - MOMENTUM_LOOKBACK].close - 1
    assert momentum_score(rows, 252) == expected
    changed = list(rows)
    changed[251] = changed[251].model_copy(update={"close": 1_000_000})
    assert momentum_score(changed, 252) == expected


def test_rank_is_deterministic_tie_broken_and_top_ten_positive_only():
    scores = {f"S{i:02d}": 1.0 for i in range(12)} | {"NEG": -1}
    assert rank_relative_strength(scores) == tuple(f"S{i:02d}" for i in range(10))


def test_month_end_signal_executes_at_later_open_not_same_close():
    result = run({"A": history("A")}, end=date(2020, 3, 31))
    signal_day = min(result.monthly_selections)
    first_buy = next(item for item in result.execution_log if item.startswith("BUY"))
    assert date.fromisoformat(first_buy.rsplit(":", 1)[1]) > signal_day


def test_fewer_than_ten_qualifiers_leaves_cash():
    result = run({"A": history("A", .3), "B": history("B", .2)})
    assert max(map(len, result.monthly_selections.values())) == 2
    assert result.ending_cash > 700_000


def test_missing_next_open_defers_only_that_symbol():
    missing = {date(2020, 2, 3)}
    data = {"A": history("A", .3, remove=missing), "B": history("B", .2)}
    result = run(data, end=date(2020, 3, 31))
    assert result.deferred_orders >= 1
    assert any(item.startswith("BUY:B:2020-02-03") for item in result.execution_log)


def test_late_listing_does_not_truncate_calendar():
    old = history("OLD")
    late = [row for row in history("LATE") if row.date.date() >= date(2020, 5, 1)]
    assert run({"OLD": old}).calendar_dates == run({"OLD": old, "LATE": late}).calendar_dates


def test_sells_precede_buys_on_each_rebalance_day():
    data = {f"S{i}": history(f"S{i}", slope=(i - 5) * .05) for i in range(12)}
    result = run(data, end=date(2020, 12, 31))
    by_day = {}
    for item in result.execution_log:
        action, _, day = item.split(":")
        by_day.setdefault(day, []).append(action)
    for actions in by_day.values():
        if "SELL" in actions and "BUY" in actions:
            assert max(i for i, action in enumerate(actions) if action == "SELL") < min(
                i for i, action in enumerate(actions) if action == "BUY")


def test_holdout_and_future_prices_cannot_change_development():
    base = run({"A": history("A", count=2200)}, end=date(2025, 8, 29))
    changed = run({"A": history("A", count=2200, future_delta=999999)}, end=date(2025, 8, 29))
    assert base.total_pnl == changed.total_pnl
    assert base.monthly_selections == changed.monthly_selections


def test_prices_after_a_signal_cannot_change_that_historical_rank():
    rows = history("A")
    changed = [
        row.model_copy(update={"close": row.close * 100})
        if row.date.date() >= date(2020, 4, 1) else row
        for row in rows
    ]
    base = run({"A": rows}, end=date(2020, 6, 30))
    future_changed = run({"A": changed}, end=date(2020, 6, 30))
    for signal_day in base.monthly_selections:
        if signal_day < date(2020, 4, 1):
            assert base.monthly_selections[signal_day] == future_changed.monthly_selections[signal_day]


def test_future_membership_requires_explicit_retrospective_mode():
    members = [UniverseMember(
        as_of=date(2026, 1, 1), index_name="NIFTY 50", symbol="A",
    )]
    with pytest.raises(ValueError, match="explicit retrospective"):
        evaluate_relative_strength(
            {"A": history("A")}, V3_STEP5_PORTFOLIO_CONFIG,
            development_start=date(2020, 1, 1), development_end=date(2020, 6, 30),
            universe_members=members,
        )


def test_dp_fees_raise_costs_and_matching_calendar_is_preserved():
    data = {"A": history("A", .3), "B": history("B", .2)}
    base = run(data)
    schedule = V3_STEP5_PORTFOLIO_CONFIG.fee_schedule.model_copy(update={
        "dp_charge_per_sell": Decimal("20"),
    })
    dp = evaluate_relative_strength(
        data, V3_STEP5_PORTFOLIO_CONFIG.model_copy(update={"fee_schedule": schedule}),
        development_start=date(2020, 1, 1), development_end=date(2020, 6, 30),
        retrospective_static_membership=True,
    )
    assert dp.calendar_dates == base.calendar_dates
    assert dp.transaction_costs >= base.transaction_costs


def test_benchmark_and_strategy_use_declared_cohort_dates():
    result = run({"A": history("A")})
    assert result.calendar_dates[0] == date(2020, 1, 1)
    assert result.calendar_dates[-1] == date(2020, 6, 30)
    assert result.reserved_holdout_start == date(2025, 9, 1)
    first_signal = min(day for day, selected in result.monthly_selections.items() if selected)
    assert result.benchmark_start_date > first_signal
