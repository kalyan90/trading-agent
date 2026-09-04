#!/usr/bin/env python3
"""Plan, paper-execute, value, or report the V5 daily control plane."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from trading_agent.execution.v4_paper import PaperMode, PriceEvidence
from trading_agent.execution.v5_daily import (
    ClosingMark,
    DailyConfig,
    TargetIntent,
    V5DailyCoordinator,
)


def load(path: Path | None) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path else {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "execute", "mark", "status"))
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--signal-date", type=date.fromisoformat)
    parser.add_argument("--inception", type=date.fromisoformat, required=True)
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--max-positions", type=int, default=10)
    parser.add_argument("--max-order-value", type=float)
    parser.add_argument("--dp-charge", type=float, default=0.0)
    parser.add_argument("--mode", choices=("dry-run", "paper"), default="dry-run")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    args = parser.parse_args()
    coordinator = V5DailyCoordinator(DailyConfig(
        inception=args.inception, initial_capital=args.capital,
        max_positions=args.max_positions, max_order_value=args.max_order_value,
        dp_charge_per_sell=args.dp_charge, mode=PaperMode(args.mode),
    ), args.journal, args.state)
    payload = load(args.input)

    if args.command == "plan":
        if args.signal_date is None or args.input is None:
            raise SystemExit("plan requires --signal-date and --input")
        output = coordinator.create_plan(
            args.signal_date,
            [TargetIntent.model_validate(item) for item in payload.get("intents", [])],
        ).model_dump(mode="json")
    elif args.command == "execute":
        if args.signal_date is None or args.as_of is None or args.input is None:
            raise SystemExit("execute requires --signal-date, --as-of, and --input")
        results = coordinator.execute(
            f"v5.1-{args.signal_date.isoformat()}", args.as_of,
            [PriceEvidence.model_validate(item) for item in payload.get("prices", [])],
        )
        output = {"results": [item.model_dump(mode="json") for item in results]}
    elif args.command == "mark":
        if args.as_of is None or args.input is None or payload.get("benchmark_close") is None:
            raise SystemExit("mark requires --as-of, --input, and benchmark_close")
        output = coordinator.mark_to_market(
            args.as_of,
            [ClosingMark.model_validate(item) for item in payload.get("marks", [])],
            benchmark_close=float(payload["benchmark_close"]),
        ).model_dump(mode="json")
    else:
        output = coordinator.status()
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
