"""Read-only data readiness checks for a prospective V4 month-end run."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from statistics import median

from pydantic import BaseModel, ConfigDict

from trading_agent.core.equity import EquityInstrument
from trading_agent.core.universe import active_symbols
from trading_agent.data.quality import DatasetManifest, file_sha256
from trading_agent.execution.v4_input import V4_INDEXES
from trading_agent.research.relative_strength import MOMENTUM_LOOKBACK, REGIME_SMA_PERIOD


class V4ReadinessReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal_date: date
    as_of: date
    active_symbols: int
    history_ready_symbols: int
    next_open_symbols: int
    membership_dates: dict[str, date]
    equity_latest_date: date | None
    index_latest_date: date | None
    manifest_files: int
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    ready: bool


def check_v4_data_readiness(
    histories,
    regime_history,
    members,
    *,
    signal_date: date,
    as_of: date,
    data_dir: Path | None = None,
) -> V4ReadinessReport:
    """Explain whether local evidence can generate a prospective monthly input."""
    blockers: list[str] = []
    warnings: list[str] = []
    if as_of <= signal_date:
        blockers.append("as_of must be later than signal_date")

    membership_dates = {}
    for index_name in sorted(V4_INDEXES):
        dates = [member.as_of for member in members
                 if member.index_name == index_name and member.as_of <= signal_date]
        if not dates:
            blockers.append(f"no {index_name} membership snapshot known by signal_date")
        else:
            membership_dates[index_name] = max(dates)
    try:
        eligible = active_symbols(members, signal_date, set(V4_INDEXES), require_snapshot=True)
    except ValueError as error:
        eligible = set()
        blockers.append(str(error))

    index_rows = sorted(regime_history, key=lambda row: row.date)
    index_by_day = {row.date.date(): index for index, row in enumerate(index_rows)}
    regime_index = index_by_day.get(signal_date)
    if regime_index is None:
        blockers.append("NIFTY 50 has no close on signal_date")
    elif regime_index + 1 < REGIME_SMA_PERIOD:
        blockers.append("NIFTY 50 lacks 200 sessions through signal_date")

    history_ready = 0
    next_open = 0
    latest_equity_dates = []
    missing_history = []
    missing_signal = []
    insufficient_history = []
    below_liquidity = []
    minimum_volume = EquityInstrument(symbol="DEFAULT").minimum_median_volume
    for symbol in sorted(eligible):
        rows = sorted(histories.get(symbol, ()), key=lambda row: row.date)
        if not rows:
            missing_history.append(symbol)
            continue
        latest_equity_dates.append(rows[-1].date.date())
        by_day = {row.date.date(): index for index, row in enumerate(rows)}
        index = by_day.get(signal_date)
        if index is None:
            missing_signal.append(symbol)
        elif index < MOMENTUM_LOOKBACK:
            insufficient_history.append(symbol)
        else:
            volumes = [row.volume for row in rows[:index + 1] if row.volume is not None]
            if volumes and median(volumes) >= minimum_volume:
                history_ready += 1
            else:
                below_liquidity.append(symbol)
        if any(signal_date < row.date.date() <= as_of for row in rows):
            next_open += 1

    def summarize(symbols, detail):
        if symbols:
            sample = ", ".join(symbols[:5])
            suffix = "..." if len(symbols) > 5 else ""
            warnings.append(f"{len(symbols)} symbols {detail}: {sample}{suffix}")

    summarize(missing_history, "have no local equity history")
    summarize(missing_signal, "have no row on signal_date")
    summarize(insufficient_history, "have fewer than 252 prior sessions")
    summarize(below_liquidity, "are below the frozen liquidity gate")

    if not eligible:
        blockers.append("prospective active universe is empty")
    elif history_ready == 0:
        blockers.append("no active symbol has signal-date history ready")
    if eligible and next_open == 0:
        blockers.append("no active symbol has later opening-price evidence")
    elif next_open < history_ready:
        warnings.append(
            f"next-open evidence available for {next_open} of {history_ready} history-ready symbols"
        )

    manifests = 0
    if data_dir is not None:
        csv_paths = sorted(data_dir.glob("*_equity.csv"))
        for csv_path in csv_paths:
            manifest_path = csv_path.with_suffix(".manifest.json")
            if not manifest_path.is_file():
                blockers.append(f"{csv_path.name}: manifest missing")
                continue
            manifests += 1
            try:
                manifest = DatasetManifest.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )
            except Exception:
                blockers.append(f"{manifest_path.name}: invalid manifest")
                continue
            if manifest.sha256 != file_sha256(csv_path):
                blockers.append(f"{csv_path.name}: checksum differs from manifest")
        if not csv_paths:
            blockers.append("equity data directory has no histories")

    return V4ReadinessReport(
        signal_date=signal_date, as_of=as_of, active_symbols=len(eligible),
        history_ready_symbols=history_ready, next_open_symbols=next_open,
        membership_dates=membership_dates,
        equity_latest_date=max(latest_equity_dates) if latest_equity_dates else None,
        index_latest_date=index_rows[-1].date.date() if index_rows else None,
        manifest_files=manifests, blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)), ready=not blockers,
    )
