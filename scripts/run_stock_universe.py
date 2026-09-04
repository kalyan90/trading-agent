"""Run frozen V2 walk-forward research across locally stored stock histories."""

import argparse
from pathlib import Path

from trading_agent.core.config import V2_CONFIG
from trading_agent.data.equity import load_equity_directory
from trading_agent.research.universe import evaluate_stock_universe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/stocks"))
    args = parser.parse_args()
    results = evaluate_stock_universe(load_equity_directory(args.data_dir), V2_CONFIG)
    print("symbol,observations,windows,accepted,pnl,trades,benchmark,excess")
    for item in results:
        print(f"{item.symbol},{item.observations},{item.windows},"
              f"{item.accepted_windows},{item.total_oos_pnl:.2f},"
              f"{item.total_oos_trades},{item.benchmark_pnl:.2f},"
              f"{item.excess_pnl:.2f}")


if __name__ == "__main__":
    main()
