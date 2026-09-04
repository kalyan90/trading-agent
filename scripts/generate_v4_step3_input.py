#!/usr/bin/env python3
"""Generate locked V4 Step 3 month-end evidence from validated local data."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_agent.execution.v4_input import load_and_build_v4_decision_input


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signal-date", type=parse_date, required=True)
    parser.add_argument("--as-of", type=parse_date, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data/stocks_step5_adjusted"))
    parser.add_argument("--index-dir", type=Path, default=Path("data"))
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = load_and_build_v4_decision_input(
        args.data_dir,
        args.index_dir,
        args.universe,
        signal_date=args.signal_date,
        as_of=args.as_of,
    )
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing evidence: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        payload.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()
