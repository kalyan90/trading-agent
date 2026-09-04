"""Run the fixed V3 Step 4 shared-portfolio and friction comparisons."""

import argparse
from pathlib import Path

from trading_agent.core.config import V2_CONFIG
from trading_agent.core.equity import V3_STEP4_PORTFOLIO_CONFIG
from trading_agent.data.equity import load_equity_directory
from trading_agent.data.quality import validate_equity_history
from trading_agent.data.universe import load_universe_snapshots
from trading_agent.research.equity_portfolio import (
    evaluate_equity_portfolio, run_robustness_scenarios,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/stocks"))
    parser.add_argument(
        "--universe", type=Path,
        default=Path("data/universe/nifty_100_bank_constituents_2026-09-04.csv"),
    )
    args = parser.parse_args()
    histories = load_equity_directory(args.data_dir)
    if not histories:
        parser.error(f"no *_equity.csv histories found in {args.data_dir}")
    print("V3 Step 4 equity data quality")
    for symbol, rows in sorted(histories.items()):
        report = validate_equity_history(rows)
        print(
            f"{symbol}: rows={report.observations} dates={report.first_date}.."
            f"{report.last_date} passed={report.passed} jumps={report.large_return_jumps}"
        )
    print("\nCurrent-membership snapshot warning: retrospective results have survivorship bias.")
    results = run_robustness_scenarios(
        histories, V2_CONFIG, V3_STEP4_PORTFOLIO_CONFIG,
        point_in_time_membership=False,
    )
    print("scenario,pnl,return_pct,max_dd,sharpe,trades,win_rate,exposure,benchmark,excess")
    for name, result in results.items():
        print(
            f"{name},{result.total_pnl:.2f},{result.total_return:.2f},"
            f"{result.max_drawdown:.2f},{result.annualized_sharpe:.3f},"
            f"{result.completed_trades},{result.win_rate:.2f},"
            f"{result.exposure_percent:.2f},{result.benchmark_pnl:.2f},"
            f"{result.excess_pnl:.2f}"
        )
    base = results["base"]
    print(
        f"accepted_symbol_windows={base.accepted_symbol_windows}/"
        f"{base.total_symbol_windows} turnover={base.turnover:.2f} "
        f"modeled_costs={base.transaction_costs:.2f} rejected_orders={base.rejected_orders}"
    )
    print(f"reserved_holdout={base.reserved_holdout_start} onward (not evaluated)")
    print("yearly_pnl=" + ", ".join(
        f"{year}:{pnl:.2f}" for year, pnl in base.yearly_pnl.items()
    ))
    print("\nPer-symbol shared-engine diagnostics (independent ₹10 lakh sleeves)")
    print("symbol,pnl,max_dd,trades,benchmark,excess,accepted_windows")
    single_config = V3_STEP4_PORTFOLIO_CONFIG.model_copy(update={
        "max_positions": 1, "allocation_fraction": 1.0,
    })
    for symbol, rows in sorted(histories.items()):
        result = evaluate_equity_portfolio(
            {symbol: rows}, V2_CONFIG, single_config,
            point_in_time_membership=False,
        )
        print(
            f"{symbol},{result.total_pnl:.2f},{result.max_drawdown:.2f},"
            f"{result.completed_trades},{result.benchmark_pnl:.2f},"
            f"{result.excess_pnl:.2f},{result.accepted_symbol_windows}/"
            f"{result.total_symbol_windows}"
        )
    members = load_universe_snapshots(args.universe)
    print("\nCurrent-snapshot group diagnostics")
    print("index,symbols,pnl,max_dd,benchmark,excess")
    for index_name in ("NIFTY 50", "NIFTY NEXT 50", "NIFTY BANK"):
        group_symbols = sorted({
            member.symbol for member in members
            if member.index_name == index_name and member.symbol in histories
        })
        if not group_symbols:
            print(f"{index_name},0,not-run,not-run,not-run,not-run")
            continue
        result = evaluate_equity_portfolio(
            {symbol: histories[symbol] for symbol in group_symbols},
            V2_CONFIG, V3_STEP4_PORTFOLIO_CONFIG,
            point_in_time_membership=False,
        )
        print(
            f"{index_name},{len(group_symbols)},{result.total_pnl:.2f},"
            f"{result.max_drawdown:.2f},{result.benchmark_pnl:.2f},"
            f"{result.excess_pnl:.2f}"
        )


if __name__ == "__main__":
    main()
