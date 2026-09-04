#!/usr/bin/env python3
"""Check local data readiness before generating a V4 monthly decision."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_agent.data.equity import load_equity_directory
from trading_agent.data.index import load_nifty50_price_history
from trading_agent.data.universe import load_universe_snapshots
from trading_agent.execution.v4_readiness import check_v4_data_readiness


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signal-date", type=date.fromisoformat, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data/stocks_step5_adjusted"))
    parser.add_argument("--index-dir", type=Path, default=Path("data"))
    parser.add_argument("--universe", type=Path, required=True)
    args = parser.parse_args()
    report = check_v4_data_readiness(
        load_equity_directory(args.data_dir),
        load_nifty50_price_history(args.index_dir),
        load_universe_snapshots(args.universe),
        signal_date=args.signal_date, as_of=args.as_of, data_dir=args.data_dir,
    )
    print(report.model_dump_json(indent=2))
    if not report.ready:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
