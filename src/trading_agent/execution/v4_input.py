"""Deterministic evidence generation for the frozen V4 paper workflow."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from statistics import median

from pydantic import BaseModel, ConfigDict

from trading_agent.core.equity import EquityInstrument
from trading_agent.core.universe import active_symbols
from trading_agent.data.equity import load_equity_directory
from trading_agent.data.index import load_nifty50_price_history
from trading_agent.data.universe import load_universe_snapshots
from trading_agent.research.relative_strength import (
    MOMENTUM_LOOKBACK,
    REGIME_SMA_PERIOD,
    momentum_score,
)


V4_INDEXES = frozenset({"NIFTY 50", "NIFTY NEXT 50", "NIFTY BANK"})


class V4DecisionInput(BaseModel):
    """Auditable JSON payload accepted by ``run_v4_step3_paper.py``."""

    model_config = ConfigDict(frozen=True)

    signal_date: date
    as_of: date
    membership_snapshot_dates: tuple[date, ...]
    indexes: tuple[str, ...]
    regime_close: float
    regime_sma200: float
    candidates: tuple[dict, ...]
    prices: tuple[dict, ...]


def build_v4_decision_input(
    histories,
    regime_history,
    members,
    *,
    signal_date: date,
    as_of: date,
    indexes: set[str] | frozenset[str] = V4_INDEXES,
) -> V4DecisionInput:
    """Build one month-end payload without reading beyond either evidence date."""
    if as_of <= signal_date:
        raise ValueError("as_of must be later than signal_date for next-open evidence")

    known_members = [member for member in members if member.as_of <= signal_date]
    if not known_members:
        raise ValueError("no universe snapshot known on or before signal_date")
    eligible = active_symbols(members, signal_date, set(indexes), require_snapshot=True)

    regime_rows = sorted(
        (row for row in regime_history if row.date.date() <= signal_date),
        key=lambda row: row.date,
    )
    if not regime_rows or regime_rows[-1].date.date() != signal_date:
        raise ValueError("NIFTY 50 has no close on signal_date")
    if len(regime_rows) < REGIME_SMA_PERIOD:
        raise ValueError("NIFTY 50 has insufficient 200-session regime history")
    regime_window = regime_rows[-REGIME_SMA_PERIOD:]

    scores: dict[str, float] = {}
    prices: list[dict] = []
    default_instrument = EquityInstrument(symbol="DEFAULT")
    for symbol, unsorted_rows in sorted(histories.items()):
        rows = sorted(unsorted_rows, key=lambda row: row.date)
        by_day = {row.date.date(): index for index, row in enumerate(rows)}
        signal_index = by_day.get(signal_date)
        if symbol in eligible and signal_index is not None and signal_index >= MOMENTUM_LOOKBACK:
            known_rows = rows[:signal_index + 1]
            volumes = [row.volume for row in known_rows if row.volume is not None]
            if (volumes and median(volumes) >= default_instrument.minimum_median_volume):
                score = momentum_score(rows, signal_index)
                if score is not None and score > 0:
                    scores[symbol] = score

        later = next(
            (row for row in rows
             if signal_date < row.date.date() <= as_of),
            None,
        )
        if later is not None:
            prices.append({
                "symbol": symbol,
                "session_date": later.date.date().isoformat(),
                "open": later.open,
            })

    ranked = sorted(scores, key=lambda symbol: (-scores[symbol], symbol))
    candidates = tuple({
        "symbol": symbol,
        "rank": rank,
        "momentum": scores[symbol],
        "member": True,
        "has_history": True,
    } for rank, symbol in enumerate(ranked, start=1))
    snapshot_dates = tuple(sorted({member.as_of for member in known_members}))
    return V4DecisionInput(
        signal_date=signal_date,
        as_of=as_of,
        membership_snapshot_dates=snapshot_dates,
        indexes=tuple(sorted(indexes)),
        regime_close=regime_window[-1].close,
        regime_sma200=sum(row.close for row in regime_window) / REGIME_SMA_PERIOD,
        candidates=candidates,
        prices=tuple(prices),
    )


def load_and_build_v4_decision_input(
    data_dir: Path,
    index_dir: Path,
    universe_path: Path,
    *,
    signal_date: date,
    as_of: date,
) -> V4DecisionInput:
    """Load validated repository datasets and build a V4 decision payload."""
    return build_v4_decision_input(
        load_equity_directory(data_dir),
        load_nifty50_price_history(index_dir),
        load_universe_snapshots(universe_path),
        signal_date=signal_date,
        as_of=as_of,
    )
