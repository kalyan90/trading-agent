"""Run V3 Step 5 without reading the reserved 250-common-session tail."""

import argparse
from pathlib import Path

from trading_agent.core.config import V2_CONFIG
from trading_agent.core.equity import V3_STEP5_PORTFOLIO_CONFIG
from trading_agent.data.equity import load_equity_directory
from trading_agent.data.quality import validate_equity_history
from trading_agent.data.universe import load_universe_snapshots
from trading_agent.research.equity_portfolio import (
    evaluate_equity_portfolio, run_robustness_scenarios,
)


GROUPS = ("NIFTY 50", "NIFTY NEXT 50", "NIFTY BANK")


def line(name, result):
    return (
        f"{name},{len(result.symbols)},{result.total_pnl:.2f},"
        f"{result.total_return:.2f},{result.max_drawdown:.2f},"
        f"{result.annualized_sharpe:.3f},{result.completed_trades},"
        f"{result.transaction_costs:.2f},{result.benchmark_pnl:.2f},"
        f"{result.excess_pnl:.2f},{result.membership_status}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/stocks_adjusted"))
    parser.add_argument(
        "--universe", type=Path,
        default=Path("data/universe/nifty_100_bank_constituents_2026-09-04.csv"),
    )
    args = parser.parse_args()
    histories = load_equity_directory(args.data_dir)
    members = load_universe_snapshots(args.universe)
    if not histories:
        parser.error("no validated adjusted histories available")
    for symbol, rows in histories.items():
        if not validate_equity_history(rows).passed:
            parser.error(f"{symbol}: failed quality validation")

    minimum_rows = (V2_CONFIG.train_size + V2_CONFIG.test_size
                    + V3_STEP5_PORTFOLIO_CONFIG.reserved_holdout_sessions)
    excluded_short = sorted(
        symbol for symbol, rows in histories.items() if len(rows) < minimum_rows
    )
    histories = {
        symbol: rows for symbol, rows in histories.items() if len(rows) >= minimum_rows
    }
    print(f"excluded_short_history={','.join(excluded_short) or 'none'}")

    by_group = {
        group: sorted({m.symbol for m in members if m.index_name == group} & histories.keys())
        for group in GROUPS
    }
    print("V3 Step 5 development comparison (current snapshot; retrospective bias)")
    print("name,symbols,pnl,return_pct,max_dd,sharpe,trades,fees,benchmark,excess,membership")
    for group, symbols in by_group.items():
        if not symbols:
            print(f"{group},0,unavailable: no local adjusted histories")
            continue
        result = evaluate_equity_portfolio(
            {s: histories[s] for s in symbols}, V2_CONFIG, V3_STEP5_PORTFOLIO_CONFIG,
        )
        print(line(group, result))

    combined_symbols = sorted(set().union(*by_group.values()))
    combined_data = {s: histories[s] for s in combined_symbols}
    results = run_robustness_scenarios(
        combined_data, V2_CONFIG, V3_STEP5_PORTFOLIO_CONFIG,
    )
    for name, result in results.items():
        print(line(f"COMBINED_{name}", result))
    base = results["base"]
    print(f"reserved_holdout={base.reserved_holdout_start} onward; NOT EVALUATED")
    print("yearly_pnl=" + ",".join(f"{y}:{p:.2f}" for y, p in base.yearly_pnl.items()))
    print("coverage=" + ",".join(f"{g}:{len(s)}" for g, s in by_group.items()))
    overlap = sorted(set(by_group["NIFTY 50"]) & set(by_group["NIFTY BANK"]))
    print(f"deduplicated_combined={len(combined_symbols)} overlap=" + ",".join(overlap))
    print("individual_symbol_contribution")
    print("symbol,pnl,trades,fees,benchmark,excess")
    single = V3_STEP5_PORTFOLIO_CONFIG.model_copy(update={
        "max_positions": 1, "allocation_fraction": 1.0,
    })
    contributions = []
    for symbol in combined_symbols:
        try:
            result = evaluate_equity_portfolio(
                {symbol: histories[symbol]}, V2_CONFIG, single,
            )
        except ValueError as error:
            print(f"{symbol},unavailable:{error}")
            continue
        contributions.append((symbol, result.total_pnl))
        print(
            f"{symbol},{result.total_pnl:.2f},{result.completed_trades},"
            f"{result.transaction_costs:.2f},{result.benchmark_pnl:.2f},"
            f"{result.excess_pnl:.2f}"
        )
    absolute = sum(abs(value) for _, value in contributions)
    concentration = max((abs(value) for _, value in contributions), default=0) / absolute
    print(f"largest_absolute_contribution_share={concentration:.4f}")


if __name__ == "__main__":
    main()
