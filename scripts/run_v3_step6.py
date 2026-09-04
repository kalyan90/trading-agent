"""Run V3 Step 6 dynamic-calendar cohorts without touching the reserved tail."""

import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path

from trading_agent.core.config import V2_CONFIG
from trading_agent.core.equity import V3_STEP5_PORTFOLIO_CONFIG
from trading_agent.data.equity import load_equity_directory
from trading_agent.data.universe import load_universe_snapshots
from trading_agent.research.dynamic_equity_portfolio import evaluate_dynamic_equity_portfolio


GROUPS = ("NIFTY 50", "NIFTY NEXT 50", "NIFTY BANK")
COHORTS = {
    "2020_2021": (date(2020, 1, 1), date(2021, 12, 31)),
    "2022_2023": (date(2022, 1, 1), date(2023, 12, 29)),
    "2024_cutoff": (date(2024, 1, 1), date(2025, 8, 29)),
}
HOLDOUT_START = date(2025, 9, 1)


def eligible_for_start(histories, start):
    result = {}
    for symbol, rows in histories.items():
        if any(row.date.date() <= start for row in rows) and any(row.date.date() >= start for row in rows):
            result[symbol] = rows
    return result


def result_line(cohort, group, result):
    breadth = (sum(value > 0 for value in result.contributions.values())
               / len(result.contributions) * 100 if result.contributions else 0)
    return (
        f"{cohort},{group},{len(result.symbols)},{result.calendar_start},"
        f"{result.calendar_end},{result.sessions},{result.total_pnl:.2f},"
        f"{result.total_return:.2f},{result.max_drawdown:.2f},"
        f"{result.annualized_sharpe:.3f},{result.completed_trades},"
        f"{result.exposure_percent:.2f},{result.turnover:.2f},"
        f"{result.transaction_costs:.2f},{result.benchmark_pnl:.2f},"
        f"{result.excess_pnl:.2f},{breadth:.2f}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/stocks_step5_adjusted"))
    parser.add_argument("--universe", type=Path, default=Path(
        "data/universe/nifty_100_bank_constituents_2026-09-04.csv"))
    args = parser.parse_args()
    histories = load_equity_directory(args.data_dir)
    members = load_universe_snapshots(args.universe)
    member_groups = {
        group: {member.symbol for member in members if member.index_name == group}
        for group in GROUPS
    }
    member_groups["COMBINED"] = set().union(*member_groups.values())
    print("mode=retrospective_current_snapshot; historical membership unavailable")
    print("dividends=unavailable; benchmarks are price return only")
    print("cohort,group,symbols,start,end,sessions,pnl,return_pct,max_dd,sharpe,trades,exposure_pct,turnover,fees,benchmark,excess,positive_contribution_pct")
    combined_results = {}
    for cohort, (start, end) in COHORTS.items():
        calendars = []
        for group in (*GROUPS, "COMBINED"):
            selected = eligible_for_start({
                symbol: rows for symbol, rows in histories.items()
                if symbol in member_groups[group]
            }, start)
            result = evaluate_dynamic_equity_portfolio(
                selected, V2_CONFIG, V3_STEP5_PORTFOLIO_CONFIG,
                development_start=start, development_end=end,
                reserved_holdout_start=HOLDOUT_START, universe_members=members,
                indexes={group} if group != "COMBINED" else set(GROUPS),
                retrospective_static_membership=True,
            )
            print(result_line(cohort, group, result))
            calendars.append(result.calendar_dates)
            if group == "COMBINED":
                combined_results[cohort] = result
        if any(calendar != calendars[0] for calendar in calendars[1:]):
            raise RuntimeError(f"{cohort}: group calendars are not identical")

    long_start, long_end = date(2020, 1, 1), date(2025, 8, 29)
    long_data = eligible_for_start({
        symbol: rows for symbol, rows in histories.items()
        if symbol in member_groups["COMBINED"]
    }, long_start)
    scenarios = {
        "base": V3_STEP5_PORTFOLIO_CONFIG,
        "double_slippage": V3_STEP5_PORTFOLIO_CONFIG.model_copy(update={"slippage": .10}),
        "double_statutory_costs": V3_STEP5_PORTFOLIO_CONFIG.model_copy(update={
            "fee_schedule": V3_STEP5_PORTFOLIO_CONFIG.fee_schedule.model_copy(update={
                "fee_multiplier": Decimal("2"),
            }),
        }),
        "dp_15_50": V3_STEP5_PORTFOLIO_CONFIG.model_copy(update={
            "fee_schedule": V3_STEP5_PORTFOLIO_CONFIG.fee_schedule.model_copy(update={
                "dp_charge_per_sell": Decimal("15.50"),
                "dp_charge_assumption": "declared illustrative broker scenario",
            }),
        }),
        "dp_25": V3_STEP5_PORTFOLIO_CONFIG.model_copy(update={
            "fee_schedule": V3_STEP5_PORTFOLIO_CONFIG.fee_schedule.model_copy(update={
                "dp_charge_per_sell": Decimal("25"),
                "dp_charge_assumption": "declared illustrative higher broker scenario",
            }),
        }),
    }
    print("long_history_scenarios")
    long_results = {}
    for name, config in scenarios.items():
        result = evaluate_dynamic_equity_portfolio(
            long_data, V2_CONFIG, config, development_start=long_start,
            development_end=long_end, reserved_holdout_start=HOLDOUT_START,
            universe_members=members, indexes=set(GROUPS),
            retrospective_static_membership=True,
        )
        long_results[name] = result
        print(result_line("2020_cutoff", name, result))
        print("yearly=" + ",".join(f"{year}:{pnl:.2f}" for year, pnl in result.yearly_pnl.items()))

    base = long_results["base"]
    cohort_values = list(combined_results.values())
    criteria = {
        "long_history_nonpositive": base.total_pnl <= 0,
        "cohort_return_breadth_le_one_third": sum(r.total_pnl > 0 for r in cohort_values) <= 1,
        "cohort_benchmark_breadth_le_one_third": sum(r.excess_pnl > 0 for r in cohort_values) <= 1,
        "drawdown_at_least_10pct": base.max_drawdown >= 100_000,
        "positive_contribution_breadth_below_half": (
            sum(v > 0 for v in base.contributions.values())
            < len(base.contributions) / 2 if base.contributions else True
        ),
    }
    # Retire when two or more independent pillars fail; continuation requires
    # passing at least four of breadth, cohort consistency, benchmark capture,
    # cost robustness, and drawdown control.
    triggered = sum(criteria.values()) >= 2
    print("retirement_rule=" + ",".join(f"{key}:{value}" for key, value in criteria.items()))
    print(f"retire_trend_momentum={triggered} failures={sum(criteria.values())}/5 threshold=2")
    print(f"reserved_holdout={HOLDOUT_START} onward NOT EVALUATED")


if __name__ == "__main__":
    main()
