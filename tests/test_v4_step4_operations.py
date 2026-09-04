import json
from datetime import date, datetime

import pytest

from trading_agent.core.market import MarketData
from trading_agent.execution.v4_operations import (
    V4OperationalReport,
    archive_operational_evidence,
    build_v4_operational_report,
    sha256_file,
    write_immutable_report,
)
from trading_agent.execution.v4_paper import (
    Candidate,
    PaperConfig,
    PaperMode,
    PriceEvidence,
    V4PaperCoordinator,
)


INCEPTION = date(2026, 9, 4)
SIGNAL = date(2026, 9, 30)
AS_OF = date(2026, 10, 1)


def index_rows(end=AS_OF):
    return [MarketData(
        date=datetime.combine(day, datetime.min.time()), symbol="NIFTY 50",
        open=close, high=close + 1, low=close - 1, close=close, volume=None,
    ) for day, close in ((INCEPTION, 100), (end, 105))]


def evidence(tmp_path, *, open_price=110):
    state = tmp_path / "state.json"
    journal = tmp_path / "journal.jsonl"
    input_path = tmp_path / "2026-09.json"
    coordinator = V4PaperCoordinator(
        PaperConfig(inception=INCEPTION, mode=PaperMode.PAPER), journal, state,
    )
    price = PriceEvidence(symbol="A", session_date=AS_OF, open=100)
    plan = coordinator.create_plan(
        signal_date=SIGNAL, as_of=AS_OF,
        candidates=[Candidate(symbol="A", rank=1, momentum=.25)],
        prices=[price], regime_close=101, regime_sma200=100,
    )
    coordinator.execute(plan.plan_id, AS_OF, [price])
    input_path.write_text(json.dumps({
        "signal_date": SIGNAL.isoformat(), "as_of": AS_OF.isoformat(),
        "prices": [{"symbol": "A", "session_date": AS_OF.isoformat(),
                    "open": open_price}],
    }), encoding="utf-8")
    return state, journal, input_path


def report(tmp_path, **updates):
    state, journal, input_path = evidence(tmp_path, **updates)
    return build_v4_operational_report(
        state_path=state, journal_path=journal, input_paths=[input_path],
        regime_history=index_rows(), as_of=AS_OF,
    ), state, journal, input_path


def test_report_audits_integrity_positions_costs_and_benchmark(tmp_path):
    result, state, journal, input_path = report(tmp_path)
    assert result.plans == 1
    assert result.filled_orders == 1
    assert result.expected_positions_match
    assert result.reconciliation_failures == 0
    assert result.duplicate_plan_events == 0
    assert result.configuration_unchanged
    assert result.benchmark_return_percent == 5
    assert result.market_value == 10_890  # 99 whole shares marked at 110
    assert result.net_return_percent > 0
    assert result.evidence == tuple(
        type(result.evidence[0])(path=str(path), sha256=sha256_file(path))
        for path in (state, journal, input_path)
    )
    assert not result.eligible_for_assessment
    assert not result.gates["twelve_complete_months"]
    assert result.reserved_holdout_consumed is False


def test_duplicate_and_reconciliation_failures_are_visible(tmp_path):
    result, state, journal, input_path = report(tmp_path)
    records = [json.loads(line) for line in journal.read_text().splitlines()]
    decision = next(item for item in records if item["event"] == "decision_plan")
    with journal.open("a", encoding="utf-8") as target:
        target.write(json.dumps(decision) + "\n")
        target.write(json.dumps({
            "event": "reconciliation",
            "payload": {"as_of": AS_OF.isoformat(), "mismatches": {"A": [99, 98]}},
        }) + "\n")
    failed = build_v4_operational_report(
        state_path=state, journal_path=journal, input_paths=[input_path],
        regime_history=index_rows(), as_of=AS_OF,
    )
    assert failed.duplicate_plan_events == 1
    assert failed.reconciliation_failures == 1
    assert not failed.gates["no_duplicate_events"]
    assert not failed.gates["no_reconciliation_failures"]


def test_previous_report_chains_hash_and_detects_configuration_change(tmp_path):
    first, state, journal, input_path = report(tmp_path)
    first_path = tmp_path / "first.json"
    write_immutable_report(first, first_path)
    snapshot = json.loads(state.read_text())
    snapshot["config"]["max_positions"] = 9
    state.write_text(json.dumps(snapshot), encoding="utf-8")
    second = build_v4_operational_report(
        state_path=state, journal_path=journal, input_paths=[input_path],
        regime_history=index_rows(date(2026, 11, 1)), as_of=date(2026, 11, 1),
        previous_report_path=first_path,
    )
    assert second.previous_report_sha256 == sha256_file(first_path)
    assert not second.configuration_unchanged
    assert not second.gates["configuration_unchanged"]


def test_report_refuses_overwrite_future_input_and_unpriced_position(tmp_path):
    result, state, journal, input_path = report(tmp_path)
    output = tmp_path / "report.json"
    write_immutable_report(result, output)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_immutable_report(result, output)
    payload = json.loads(input_path.read_text())
    payload["as_of"] = "2026-10-02"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="after report as_of"):
        build_v4_operational_report(
            state_path=state, journal_path=journal, input_paths=[input_path],
            regime_history=index_rows(), as_of=AS_OF,
        )


def test_invalid_journal_is_rejected(tmp_path):
    _, state, journal, input_path = report(tmp_path)
    journal.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid journal JSON"):
        build_v4_operational_report(
            state_path=state, journal_path=journal, input_paths=[input_path],
            regime_history=index_rows(), as_of=AS_OF,
        )


def test_archive_preserves_content_addressed_evidence(tmp_path):
    result, state, journal, input_path = report(tmp_path)
    output = tmp_path / "report.json"
    write_immutable_report(result, output)
    archived = archive_operational_evidence(
        [state, journal, input_path, output], tmp_path / "archive",
    )
    assert len(archived) == 4
    assert all(path.name.startswith(sha256_file(path)) for path in archived)
    assert archive_operational_evidence(
        [state, journal, input_path, output], tmp_path / "archive",
    ) == archived
