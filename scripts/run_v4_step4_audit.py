#!/usr/bin/env python3
"""Create an immutable V4 prospective integrity and benchmark report."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_agent.data.index import load_nifty50_price_history
from trading_agent.execution.v4_operations import (
    archive_operational_evidence,
    build_v4_operational_report,
    write_immutable_report,
)


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=parse_date, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--index-dir", type=Path, default=Path("data"))
    parser.add_argument("--previous-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build_v4_operational_report(
        state_path=args.state,
        journal_path=args.journal,
        input_paths=args.input,
        regime_history=load_nifty50_price_history(args.index_dir),
        as_of=args.as_of,
        previous_report_path=args.previous_report,
    )
    write_immutable_report(report, args.output)
    archive_operational_evidence(
        [args.state, args.journal, *args.input, args.output], args.archive_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
