from datetime import date

import pytest

from trading_agent.execution.broker import OrderStatus
from trading_agent.execution.v4_paper import PaperMode, PriceEvidence
from trading_agent.execution.v5_daily import (
    ClosingMark,
    DailyAction,
    DailyConfig,
    TargetIntent,
    V5DailyCoordinator,
)


INCEPTION = date(2026, 9, 4)
DAY1 = date(2026, 9, 7)
DAY2 = date(2026, 9, 8)
DAY3 = date(2026, 9, 9)


def coordinator(tmp_path, **updates):
    config = DailyConfig(inception=INCEPTION, **updates)
    return V5DailyCoordinator(config, tmp_path / "journal.jsonl", tmp_path / "state.json")


def intent(symbol, target, **updates):
    return TargetIntent(
        symbol=symbol, target_quantity=target,
        satisfiers={"data_fresh": True, "risk_clear": True}, **updates,
    )


def open_price(symbol, value, day=DAY2):
    return PriceEvidence(symbol=symbol, session_date=day, open=value)


def close_price(symbol, value, day=DAY2):
    return ClosingMark(symbol=symbol, session_date=day, close=value)


def test_daily_plan_records_buy_hold_defer_and_block_without_forcing_trades(tmp_path):
    subject = coordinator(tmp_path)
    plan = subject.create_plan(DAY1, [
        intent("BUY", 5),
        intent("HOLD", 0),
        intent("DEFER", 2, evidence_complete=False),
        TargetIntent(symbol="BLOCK", target_quantity=2,
                     satisfiers={"data_fresh": False}),
    ])
    actions = {decision.symbol: decision.action for decision in plan.decisions}
    assert actions == {
        "BLOCK": DailyAction.BLOCK,
        "BUY": DailyAction.BUY,
        "DEFER": DailyAction.DEFER,
        "HOLD": DailyAction.HOLD,
    }
    assert [order.symbol for order in plan.orders] == ["BUY"]
    assert next(item for item in plan.decisions if item.symbol == "BLOCK").failed_satisfiers == (
        "data_fresh",
    )


def test_next_open_execution_is_idempotent_and_restart_safe(tmp_path):
    subject = coordinator(tmp_path, mode=PaperMode.PAPER)
    plan = subject.create_plan(DAY1, [intent("A", 5)])
    with pytest.raises(ValueError, match="later than signal date"):
        subject.execute(plan.plan_id, DAY1, [open_price("A", 100, DAY1)])
    first = subject.execute(plan.plan_id, DAY2, [open_price("A", 100)])
    assert first[0].status == OrderStatus.FILLED
    assert subject.broker.positions() == {"A": 5}
    restored = coordinator(tmp_path, mode=PaperMode.PAPER)
    second = restored.execute(plan.plan_id, DAY2, [open_price("A", 100)])
    assert second == first
    assert restored.broker.positions() == {"A": 5}


def test_missing_open_defers_one_order_without_blocking_another(tmp_path):
    subject = coordinator(tmp_path, mode=PaperMode.PAPER)
    plan = subject.create_plan(DAY1, [intent("A", 5), intent("B", 5)])
    results = subject.execute(plan.plan_id, DAY2, [open_price("B", 100)])
    assert len(results) == 1
    assert subject.broker.positions() == {"B": 5}
    assert subject.status()["pending_orders"] == 1


def test_mark_to_market_tracks_daily_return_drawdown_fees_and_benchmark(tmp_path):
    subject = coordinator(tmp_path, mode=PaperMode.PAPER)
    plan = subject.create_plan(DAY1, [intent("A", 5)])
    subject.execute(plan.plan_id, DAY2, [open_price("A", 100)])
    first = subject.mark_to_market(
        DAY2, [close_price("A", 110)], benchmark_close=1_000,
    )
    assert first.market_value == 550
    assert first.fees > 0
    assert first.benchmark_return_percent == 0
    second = subject.mark_to_market(
        DAY3, [close_price("A", 90, DAY3)], benchmark_close=1_010,
    )
    assert second.drawdown == 100
    assert second.benchmark_return_percent == 1
    assert second.excess_return_percent < second.net_return_percent
    with pytest.raises(ValueError, match="duplicate daily metric"):
        subject.mark_to_market(DAY3, [close_price("A", 90, DAY3)], benchmark_close=1_010)


def test_open_position_requires_daily_intent_and_exact_closing_mark(tmp_path):
    subject = coordinator(tmp_path, mode=PaperMode.PAPER)
    plan = subject.create_plan(DAY1, [intent("A", 5)])
    subject.execute(plan.plan_id, DAY2, [open_price("A", 100)])
    next_plan = subject.create_plan(DAY2, [])
    assert next_plan.decisions[0].action == DailyAction.DEFER
    assert next_plan.orders == ()
    with pytest.raises(ValueError, match="lack exact-date closing marks"):
        subject.mark_to_market(DAY2, [], benchmark_close=1_000)


def test_kill_switch_and_reconciliation_mismatch_block_decisions_and_execution(tmp_path):
    subject = coordinator(tmp_path, mode=PaperMode.PAPER)
    subject.set_kill_switch()
    blocked = subject.create_plan(DAY1, [intent("A", 5)])
    assert blocked.decisions[0].action == DailyAction.BLOCK
    assert blocked.orders == ()
    with pytest.raises(RuntimeError, match="kill switch"):
        subject.execute(blocked.plan_id, DAY2, [open_price("A", 100)])

    other = coordinator(tmp_path / "other")
    other.broker._positions["DRIFT"] = 1
    mismatch = other.create_plan(DAY1, [intent("A", 5), intent("DRIFT", 0)])
    assert all(item.action == DailyAction.BLOCK for item in mismatch.decisions)


def test_buy_limit_rejects_oversized_order_but_does_not_prevent_appreciated_sale(tmp_path):
    subject = coordinator(tmp_path, mode=PaperMode.PAPER)
    oversized = subject.create_plan(DAY1, [intent("A", 100)])
    rejected = subject.execute(oversized.plan_id, DAY2, [open_price("A", 200)])[0]
    assert rejected.status == OrderStatus.REJECTED
    assert "buy order value" in rejected.reason

    other = coordinator(tmp_path / "other", mode=PaperMode.PAPER)
    buy = other.create_plan(DAY1, [intent("A", 5)])
    assert other.execute(buy.plan_id, DAY2, [open_price("A", 100)])[0].status == OrderStatus.FILLED
    sell = other.create_plan(DAY2, [intent("A", 0)])
    result = other.execute(sell.plan_id, DAY3, [open_price("A", 5_000, DAY3)])[0]
    assert result.status == OrderStatus.FILLED
    assert other.broker.positions() == {"A": 0}


def test_duplicate_days_symbols_position_limit_and_pre_inception_are_rejected(tmp_path):
    subject = coordinator(tmp_path, max_positions=1)
    with pytest.raises(ValueError, match="predates inception"):
        subject.create_plan(date(2026, 9, 3), [])
    with pytest.raises(ValueError, match="duplicate target intent"):
        subject.create_plan(DAY1, [intent("A", 1), intent("A", 2)])
    with pytest.raises(ValueError, match="maximum positions"):
        subject.create_plan(DAY1, [intent("A", 1), intent("B", 1)])
    subject.create_plan(DAY1, [intent("A", 1)])
    with pytest.raises(ValueError, match="duplicate daily decision"):
        subject.create_plan(DAY1, [intent("A", 1)])

    chronological = coordinator(tmp_path / "chronological")
    chronological.create_plan(DAY2, [intent("A", 1)])
    with pytest.raises(ValueError, match="must be chronological"):
        chronological.create_plan(DAY1, [intent("A", 1)])


def test_dry_run_records_plan_without_filling(tmp_path):
    subject = coordinator(tmp_path)
    plan = subject.create_plan(DAY1, [intent("A", 5)])
    assert subject.execute(plan.plan_id, DAY2, [open_price("A", 100)]) == []
    assert subject.broker.positions() == {}
    assert subject.status()["decision_days"] == 1
