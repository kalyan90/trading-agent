#!/usr/bin/env python3
"""Plan, locally paper-fill, or report V4 Step 3 state; never calls a network."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from trading_agent.execution.v4_paper import (
    Candidate,
    PaperConfig,
    PaperMode,
    PriceEvidence,
    V4PaperCoordinator,
)


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=("plan", "execute", "status"))
    result.add_argument("--as-of", type=parse_date, required=True)
    result.add_argument("--signal-date", type=parse_date)
    result.add_argument("--inception", type=parse_date, required=True)
    result.add_argument("--capital", type=float, default=100_000)
    result.add_argument("--max-positions", type=int, default=10)
    result.add_argument("--max-order-value", type=float)
    result.add_argument("--dp-charge", type=float, default=0.0)
    result.add_argument("--mode", choices=("dry-run", "paper"), default="dry-run")
    result.add_argument("--input", type=Path, help="Local JSON decision/price evidence")
    result.add_argument("--state", type=Path, required=True)
    result.add_argument("--journal", type=Path, required=True)
    result.add_argument("--data-dir", type=Path, help="Declared local market-data root (provenance only)")
    return result


def load_input(path: Path | None) -> dict:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    args = parser().parse_args()
    config = PaperConfig(
        initial_capital=args.capital,
        max_positions=args.max_positions,
        max_order_value=args.max_order_value,
        inception=args.inception,
        mode=PaperMode(args.mode),
        dp_charge_per_sell=args.dp_charge,
    )
    coordinator = V4PaperCoordinator(config, args.journal, args.state)
    payload = load_input(args.input)
    if args.command == "status":
        output = coordinator.status(args.as_of)
    elif args.command == "plan":
        if args.signal_date is None or args.input is None:
            raise SystemExit("plan requires --signal-date and --input")
        plan = coordinator.create_plan(
            signal_date=args.signal_date,
            as_of=args.as_of,
            candidates=[Candidate.model_validate(item) for item in payload.get("candidates", [])],
            prices=[PriceEvidence.model_validate(item) for item in payload.get("prices", [])],
            regime_close=payload.get("regime_close"),
            regime_sma200=payload.get("regime_sma200"),
        )
        output = plan.model_dump(mode="json")
    else:
        if args.signal_date is None or args.input is None:
            raise SystemExit("execute requires --signal-date and --input")
        results = coordinator.execute(
            f"v4.3-{args.signal_date:%Y-%m}", args.as_of,
            [PriceEvidence.model_validate(item) for item in payload.get("prices", [])],
        )
        output = {
            "results": [item.model_dump(mode="json") for item in results],
            "status": coordinator.status(args.as_of),
        }
    output["declared_data_dir"] = str(args.data_dir) if args.data_dir else None
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
