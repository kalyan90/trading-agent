from datetime import date

import pytest

from trading_agent.execution.broker import OrderSide, OrderStatus
from trading_agent.execution.v4_paper import (
    Candidate,
    PaperConfig,
    PaperMode,
    PriceEvidence,
    SkipReason,
    V4PaperCoordinator,
    client_order_id,
    live_broker_adapter,
)


INCEPTION = date(2026, 9, 4)
SIGNAL = date(2026, 9, 30)
OPEN = date(2026, 10, 1)


def coordinator(tmp_path, **updates):
    config = PaperConfig(inception=INCEPTION, **updates)
    return V4PaperCoordinator(config, tmp_path / "journal.jsonl", tmp_path / "state.json")


def candidate(symbol, rank, **updates):
    return Candidate(symbol=symbol, rank=rank, momentum=1 / rank, **updates)


def price(symbol, value, session_date=OPEN):
    return PriceEvidence(symbol=symbol, session_date=session_date, open=value)


def make_plan(subject, candidates, prices, **updates):
    return subject.create_plan(
        signal_date=SIGNAL, as_of=OPEN, candidates=candidates, prices=prices,
        regime_close=101, regime_sma200=100, **updates,
    )


@pytest.mark.parametrize("capital,target", [(50_000, 5_000), (100_000, 10_000), (1_000_000, 100_000)])
def test_capital_is_configurable_and_defines_fixed_target(tmp_path, capital, target):
    subject = coordinator(tmp_path, initial_capital=capital)
    plan = make_plan(subject, [candidate("A", 1)], [price("A", 100)])
    assert plan.target_allocation == target


def test_unaffordable_rank_is_skipped_and_lower_rank_selected(tmp_path):
    subject = coordinator(tmp_path)
    plan = make_plan(
        subject,
        [candidate("EXPENSIVE", 1), candidate("AFFORDABLE", 2)],
        [price("EXPENSIVE", 12_000), price("AFFORDABLE", 1_000)],
    )
    assert tuple(plan.target_quantities) == ("AFFORDABLE",)
    assert plan.target_quantities["AFFORDABLE"] == 9
    assert plan.skips[0].reason == SkipReason.UNAFFORDABLE_TARGET


def test_whole_shares_no_negative_cash_and_unused_cash_retained(tmp_path):
    subject = coordinator(tmp_path, mode=PaperMode.PAPER)
    plan = make_plan(subject, [candidate("A", 1)], [price("A", 3_000)])
    assert plan.target_quantities == {"A": 3}
    results = subject.execute(plan.plan_id, OPEN, [price("A", 3_000)])
    assert results[0].status == OrderStatus.FILLED
    assert subject.broker.positions() == {"A": 3}
    assert 90_000 < subject.broker.available_cash() < 91_000


def test_insufficient_cash_is_skipped_and_position_limit_is_enforced(tmp_path):
    subject = coordinator(tmp_path, max_positions=2)
    subject.broker.cash = 50
    plan = make_plan(
        subject,
        [candidate("A", 1), candidate("B", 2), candidate("C", 3)],
        [price("A", 100), price("B", 200), price("C", 300)],
    )
    assert plan.target_quantities == {}
    assert all(item.reason == SkipReason.INSUFFICIENT_CASH for item in plan.skips)

    other = coordinator(tmp_path / "limit", max_positions=2)
    limited = make_plan(
        other,
        [candidate("A", 1), candidate("B", 2), candidate("C", 3)],
        [price("A", 100), price("B", 200), price("C", 300)],
    )
    assert len(limited.target_quantities) == 2


def test_rank_tie_and_order_ids_are_deterministic(tmp_path):
    subject = coordinator(tmp_path)
    plan = make_plan(
        subject,
        [Candidate(symbol="B", rank=1, momentum=.5), Candidate(symbol="A", rank=1, momentum=.5)],
        [price("A", 100), price("B", 100)],
    )
    assert [item.symbol for item in plan.ranked_candidates] == ["A", "B"]
    expected = client_order_id(SIGNAL, "A", OrderSide.BUY)
    assert next(item for item in plan.orders if item.symbol == "A").client_order_id == expected
    assert expected == client_order_id(SIGNAL, "A", OrderSide.BUY)


def test_same_close_cannot_be_used_as_next_open(tmp_path):
    subject = coordinator(tmp_path)
    plan = make_plan(subject, [candidate("A", 1)], [price("A", 100, SIGNAL)])
    assert plan.orders == ()
    assert plan.skips[0].reason == SkipReason.MISSING_STALE_PRICE


def test_missing_symbol_is_deferred_without_blocking_other_fill(tmp_path):
    subject = coordinator(tmp_path, mode=PaperMode.PAPER)
    plan = make_plan(
        subject, [candidate("A", 1), candidate("B", 2)],
        [price("A", 100), price("B", 200)],
    )
    results = subject.execute(plan.plan_id, OPEN, [price("B", 200)])
    assert [result.client_order_id for result in results] == [client_order_id(SIGNAL, "B", OrderSide.BUY)]
    assert subject.status(OPEN)["pending_or_deferred_orders"] == 1


def test_prospective_inception_rejects_pre_freeze_evidence(tmp_path):
    subject = coordinator(tmp_path)
    with pytest.raises(ValueError, match="predates locked inception"):
        subject.create_plan(
            signal_date=date(2026, 8, 31), as_of=date(2026, 9, 1),
            candidates=[], prices=[], regime_close=101, regime_sma200=100,
        )


def test_historical_warmup_is_not_persisted_as_prospective_performance(tmp_path):
    subject = coordinator(tmp_path)
    plan = subject.create_plan(
        signal_date=date(2025, 8, 29), as_of=date(2025, 9, 1),
        candidates=[], prices=[], regime_close=101, regime_sma200=100,
        historical_warmup=True,
    )
    assert plan.warmup_only
    assert subject.plans == {}
    assert subject.journal.records() == []


def test_restart_restores_plan_orders_and_idempotency(tmp_path):
    subject = coordinator(tmp_path, mode=PaperMode.PAPER)
    plan = make_plan(subject, [candidate("A", 1)], [price("A", 100)])
    first = subject.execute(plan.plan_id, OPEN, [price("A", 100)])
    restored = coordinator(tmp_path, mode=PaperMode.PAPER)
    second = restored.execute(plan.plan_id, OPEN, [price("A", 100)])
    assert second == first
    assert restored.broker.positions() == subject.broker.positions()


def test_duplicate_month_decision_is_refused(tmp_path):
    subject = coordinator(tmp_path)
    make_plan(subject, [], [])
    with pytest.raises(ValueError, match="duplicate month decision"):
        make_plan(subject, [], [])


def test_missing_stale_history_membership_and_regime_reasons(tmp_path):
    subject = coordinator(tmp_path)
    plan = make_plan(
        subject,
        [candidate("MISSING", 1), candidate("STALE", 2), candidate("HISTORY", 3, has_history=False), candidate("MEMBER", 4, member=False)],
        [price("STALE", 100, date(2026, 9, 20))],
    )
    assert {item.reason for item in plan.skips} == {
        SkipReason.MISSING_STALE_PRICE, SkipReason.INSUFFICIENT_HISTORY, SkipReason.MEMBERSHIP,
    }
    other = coordinator(tmp_path / "other")
    off = other.create_plan(
        signal_date=SIGNAL, as_of=OPEN, candidates=[candidate("A", 1)], prices=[price("A", 100)],
        regime_close=100, regime_sma200=100,
    )
    assert off.skips[0].reason == SkipReason.REGIME_OFF


def test_kill_switch_risk_limit_and_reconciliation(tmp_path):
    subject = coordinator(tmp_path, mode=PaperMode.PAPER, max_order_value=5_000)
    plan = make_plan(subject, [candidate("A", 1)], [price("A", 1_000)])
    result = subject.execute(plan.plan_id, OPEN, [price("A", 1_000)])[0]
    assert result.status == OrderStatus.REJECTED
    subject.set_kill_switch()
    with pytest.raises(RuntimeError, match="kill switch"):
        subject.execute(plan.plan_id, OPEN, [price("A", 1_000)])
    subject.broker._positions["DRIFT"] = 1
    assert subject.reconcile() == {"DRIFT": (0, 1)}


def test_dry_run_is_default_and_live_adapter_is_impossible(tmp_path):
    subject = coordinator(tmp_path)
    plan = make_plan(subject, [candidate("A", 1)], [price("A", 100)])
    assert subject.execute(plan.plan_id, OPEN, [price("A", 100)]) == []
    assert subject.broker.positions() == {}
    with pytest.raises(RuntimeError, match="intentionally unavailable"):
        live_broker_adapter()


def test_future_price_mutation_cannot_change_earlier_plan(tmp_path):
    subject = coordinator(tmp_path)
    plan = make_plan(subject, [candidate("A", 1)], [price("A", 100)])
    later = price("A", 9_000, date(2026, 10, 2))
    assert plan.target_quantities == {"A": 99}
    assert later.open == 9_000
    assert subject.plans[plan.plan_id] == plan


def test_status_requires_twelve_complete_months(tmp_path):
    subject = coordinator(tmp_path)
    assert subject.status(date(2026, 10, 1))["months_observed"] == 0
    assert subject.status(date(2027, 8, 31))["eligible_for_assessment"] is False
    assert subject.status(date(2027, 9, 30))["eligible_for_assessment"] is True
