"""Integrity and performance reporting for frozen V4 prospective paper runs."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class FileDigest(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    sha256: str


class V4OperationalReport(BaseModel):
    """One immutable, checksum-backed observation report."""

    model_config = ConfigDict(frozen=True)

    as_of: date
    inception: date
    months_observed: int
    configuration_sha256: str
    previous_report_sha256: str | None
    evidence: tuple[FileDigest, ...]
    plans: int
    filled_orders: int
    rejected_orders: int
    duplicate_plan_events: int
    duplicate_order_result_events: int
    reconciliation_failures: int
    expected_positions_match: bool
    cash: float
    market_value: float
    equity: float
    net_return_percent: float
    equity_high: float
    max_drawdown: float
    max_drawdown_percent: float
    fees: float
    benchmark_start_date: date
    benchmark_end_date: date
    benchmark_return_percent: float
    excess_return_percent: float
    configuration_unchanged: bool
    eligible_for_assessment: bool
    gates: dict[str, bool]
    reserved_holdout_consumed: bool = False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _records(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid journal JSON at line {line_number}") from error
            if set(record) != {"event", "payload"}:
                raise ValueError(f"invalid journal record at line {line_number}")
            records.append(record)
    return records


def _months(inception: date, as_of: date) -> int:
    months = (as_of.year - inception.year) * 12 + as_of.month - inception.month
    if as_of.day < inception.day:
        months -= 1
    return max(0, months)


def build_v4_operational_report(
    *,
    state_path: Path,
    journal_path: Path,
    input_paths: list[Path],
    regime_history,
    as_of: date,
    previous_report_path: Path | None = None,
) -> V4OperationalReport:
    """Audit persisted paper evidence and calculate declared benchmark results."""
    if not input_paths:
        raise ValueError("at least one monthly input is required")
    paths = [state_path, journal_path, *sorted(input_paths)]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise ValueError("missing evidence: " + ", ".join(missing))

    state = json.loads(state_path.read_text(encoding="utf-8"))
    records = _records(journal_path)
    config = state["config"]
    inception = date.fromisoformat(config["inception"])
    if as_of < inception:
        raise ValueError("as_of predates prospective inception")
    config_sha = _canonical_sha256(config)

    previous = None
    previous_sha = None
    if previous_report_path is not None:
        previous = V4OperationalReport.model_validate_json(
            previous_report_path.read_text(encoding="utf-8")
        )
        if previous.as_of >= as_of:
            raise ValueError("previous report must predate as_of")
        previous_sha = sha256_file(previous_report_path)

    inputs = [json.loads(path.read_text(encoding="utf-8")) for path in input_paths]
    for payload in inputs:
        if date.fromisoformat(payload["as_of"]) > as_of:
            raise ValueError("monthly input contains evidence after report as_of")
    price_evidence = {}
    for payload in inputs:
        for item in payload.get("prices", []):
            session = date.fromisoformat(item["session_date"])
            prior = price_evidence.get(item["symbol"])
            if session <= as_of and (prior is None or session > prior[0]):
                price_evidence[item["symbol"]] = (session, float(item["open"]))

    broker = state["broker"]
    positions = {symbol: int(quantity) for symbol, quantity in broker["positions"].items()}
    unpriced = sorted(set(positions) - set(price_evidence))
    if unpriced:
        raise ValueError("positions lack current input price evidence: " + ", ".join(unpriced))
    market_value = sum(quantity * price_evidence[symbol][1]
                       for symbol, quantity in positions.items())
    cash = float(broker["cash"])
    equity = cash + market_value
    initial = float(config["initial_capital"])
    net_return = (equity / initial - 1) * 100

    prior_high = previous.equity_high if previous else initial
    prior_drawdown = previous.max_drawdown if previous else 0.0
    equity_high = max(prior_high, equity)
    max_drawdown = max(prior_drawdown, equity_high - equity)
    max_drawdown_percent = max_drawdown / equity_high * 100 if equity_high else 0.0

    index_rows = sorted(
        (row for row in regime_history if inception <= row.date.date() <= as_of),
        key=lambda row: row.date,
    )
    if not index_rows:
        raise ValueError("NIFTY 50 benchmark has no prospective observations")
    benchmark_return = (index_rows[-1].close / index_rows[0].close - 1) * 100

    plan_ids = [record["payload"]["plan_id"] for record in records
                if record["event"] == "decision_plan"]
    order_ids = [record["payload"]["client_order_id"] for record in records
                 if record["event"] == "order_result"]
    duplicates_plans = len(plan_ids) - len(set(plan_ids))
    duplicates_orders = len(order_ids) - len(set(order_ids))
    reconciliation_failures = sum(
        bool(record["payload"].get("mismatches")) for record in records
        if record["event"] == "reconciliation"
    )
    expected = {key: int(value) for key, value in state["expected_positions"].items()}
    positions_match = expected == {key: value for key, value in positions.items() if value}
    results = state["order_results"].values()
    filled = sum(item["status"] == "FILLED" for item in results)
    rejected = sum(item["status"] == "REJECTED" for item in results)
    unchanged = previous is None or previous.configuration_sha256 == config_sha
    months = _months(inception, as_of)
    gates = {
        "twelve_complete_months": months >= 12,
        "positive_net_return_after_costs": net_return > 0,
        "max_drawdown_le_20_percent": max_drawdown_percent <= 20,
        "benchmark_declared": True,
        "no_duplicate_events": duplicates_plans == 0 and duplicates_orders == 0,
        "no_reconciliation_failures": reconciliation_failures == 0 and positions_match,
        "configuration_unchanged": unchanged,
    }
    evidence = tuple(FileDigest(path=str(path), sha256=sha256_file(path)) for path in paths)
    return V4OperationalReport(
        as_of=as_of, inception=inception, months_observed=months,
        configuration_sha256=config_sha, previous_report_sha256=previous_sha,
        evidence=evidence, plans=len(state["plans"]), filled_orders=filled,
        rejected_orders=rejected, duplicate_plan_events=duplicates_plans,
        duplicate_order_result_events=duplicates_orders,
        reconciliation_failures=reconciliation_failures,
        expected_positions_match=positions_match, cash=round(cash, 2),
        market_value=round(market_value, 2), equity=round(equity, 2),
        net_return_percent=round(net_return, 6), equity_high=round(equity_high, 2),
        max_drawdown=round(max_drawdown, 2),
        max_drawdown_percent=round(max_drawdown_percent, 6),
        fees=round(float(state["fees"]), 2),
        benchmark_start_date=index_rows[0].date.date(),
        benchmark_end_date=index_rows[-1].date.date(),
        benchmark_return_percent=round(benchmark_return, 6),
        excess_return_percent=round(net_return - benchmark_return, 6),
        configuration_unchanged=unchanged,
        eligible_for_assessment=all(gates.values()), gates=gates,
    )


def write_immutable_report(report: V4OperationalReport, output: Path) -> None:
    """Write a report once; prospective evidence is never silently replaced."""
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing report: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


def archive_operational_evidence(paths: list[Path], archive_dir: Path) -> tuple[Path, ...]:
    """Preserve content-addressed copies of evidence needed to reproduce a report."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived = []
    for source in paths:
        digest = sha256_file(source)
        destination = archive_dir / f"{digest}-{source.name}"
        if destination.exists():
            if sha256_file(destination) != digest:
                raise ValueError(f"archive collision: {destination}")
        else:
            shutil.copy2(source, destination)
        archived.append(destination)
    return tuple(archived)
