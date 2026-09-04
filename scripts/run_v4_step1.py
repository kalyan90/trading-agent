"""Run the fixed V4 Step 1 cross-sectional relative-strength hypothesis."""

import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path

from trading_agent.core.equity import V3_STEP5_PORTFOLIO_CONFIG
from trading_agent.data.equity import load_equity_directory
from trading_agent.data.universe import load_universe_snapshots
from trading_agent.research.relative_strength import evaluate_relative_strength


GROUPS = ("NIFTY 50", "NIFTY NEXT 50", "NIFTY BANK")
COHORTS = {
    "2020_2021": (date(2020, 1, 1), date(2021, 12, 31)),
    "2022_2023": (date(2022, 1, 3), date(2023, 12, 29)),
    "2024_cutoff": (date(2024, 1, 1), date(2025, 8, 29)),
}
HOLDOUT_START = date(2025, 9, 1)


def at_start(histories, start):
    return {
        symbol: rows for symbol, rows in histories.items()
        if any(row.date.date() <= start for row in rows)
        and any(row.date.date() >= start for row in rows)
    }


def line(cohort, group, result):
    positive = (sum(value > 0 for value in result.contributions.values())
                / len(result.contributions) * 100 if result.contributions else 0)
    return (
        f"{cohort},{group},{len(result.symbols)},{result.calendar_dates[0]},"
        f"{result.calendar_dates[-1]},{len(result.calendar_dates)},"
        f"{result.total_pnl:.2f},{result.total_return:.2f},"
        f"{result.max_drawdown:.2f},{result.annualized_sharpe:.3f},"
        f"{result.completed_sales},{result.exposure_percent:.2f},"
        f"{result.turnover:.2f},{result.transaction_costs:.2f},"
        f"{result.ending_cash:.2f},{result.rejected_orders},"
        f"{result.deferred_orders},{result.benchmark_start_date},"
        f"{result.benchmark_pnl:.2f},"
        f"{result.excess_pnl:.2f},{positive:.2f}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/stocks_step5_adjusted"))
    parser.add_argument("--universe", type=Path, default=Path(
        "data/universe/nifty_100_bank_constituents_2026-09-04.csv"))
    args = parser.parse_args()
    histories = load_equity_directory(args.data_dir)
    members = load_universe_snapshots(args.universe)
    groups = {
        group: {member.symbol for member in members if member.index_name == group}
        for group in GROUPS
    }
    groups["COMBINED"] = set().union(*groups.values())
    print("hypothesis=12_minus_1_month_relative_strength_top10_monthly")
    print("mode=retrospective_current_snapshot; dividends=unavailable_price_return_only")
    print("cohort,group,symbols,start,end,sessions,pnl,return_pct,max_dd,sharpe,sales,exposure_pct,turnover,fees,cash,rejected,deferred,benchmark_start,benchmark,excess,positive_contribution_pct")
    combined = {}
    for cohort, (start, end) in COHORTS.items():
        calendars = []
        for group in (*GROUPS, "COMBINED"):
            data = at_start({s: histories[s] for s in groups[group] if s in histories}, start)
            result = evaluate_relative_strength(
                data, V3_STEP5_PORTFOLIO_CONFIG, development_start=start,
                development_end=end, reserved_holdout_start=HOLDOUT_START,
                universe_members=members,
                indexes={group} if group != "COMBINED" else set(GROUPS),
                retrospective_static_membership=True,
            )
            print(line(cohort, group, result))
            calendars.append(result.calendar_dates)
            if group == "COMBINED":
                combined[cohort] = result
        if any(calendar != calendars[0] for calendar in calendars[1:]):
            raise RuntimeError(f"{cohort}: group calendars differ")

    long_start, long_end = date(2020, 1, 1), date(2025, 8, 29)
    long_data = at_start({s: histories[s] for s in groups["COMBINED"] if s in histories}, long_start)
    base_schedule = V3_STEP5_PORTFOLIO_CONFIG.fee_schedule
    scenarios = {
        "base": V3_STEP5_PORTFOLIO_CONFIG,
        "double_slippage": V3_STEP5_PORTFOLIO_CONFIG.model_copy(update={"slippage": .10}),
        "double_statutory_costs": V3_STEP5_PORTFOLIO_CONFIG.model_copy(update={
            "fee_schedule": base_schedule.model_copy(update={"fee_multiplier": Decimal("2")}),
        }),
        "dp_15_50": V3_STEP5_PORTFOLIO_CONFIG.model_copy(update={
            "fee_schedule": base_schedule.model_copy(update={
                "dp_charge_per_sell": Decimal("15.50"),
                "dp_charge_assumption": "declared illustrative broker scenario",
            }),
        }),
        "dp_25": V3_STEP5_PORTFOLIO_CONFIG.model_copy(update={
            "fee_schedule": base_schedule.model_copy(update={
                "dp_charge_per_sell": Decimal("25"),
                "dp_charge_assumption": "declared illustrative higher broker scenario",
            }),
        }),
    }
    print("long_history_scenarios")
    long_results = {}
    for name, config in scenarios.items():
        result = evaluate_relative_strength(
            long_data, config, development_start=long_start,
            development_end=long_end, reserved_holdout_start=HOLDOUT_START,
            universe_members=members, indexes=set(GROUPS),
            retrospective_static_membership=True,
        )
        long_results[name] = result
        print(line("2020_cutoff", name, result))
        print("yearly=" + ",".join(f"{year}:{pnl:.2f}" for year, pnl in result.yearly_pnl.items()))

    base = long_results["base"]
    pillars = {
        "positive_2_of_3": sum(r.total_pnl > 0 for r in combined.values()) >= 2,
        "beats_benchmark_2_of_3": sum(r.excess_pnl > 0 for r in combined.values()) >= 2,
        "long_drawdown_le_20pct": base.max_drawdown <= 200_000,
        "positive_contribution_breadth_ge_50pct": (
            sum(value > 0 for value in base.contributions.values())
            >= len(base.contributions) / 2 if base.contributions else False
        ),
        "profitable_double_cost": long_results["double_statutory_costs"].total_pnl > 0,
    }
    failures = sum(not passed for passed in pillars.values())
    print("decision_pillars=" + ",".join(f"{name}:{passed}" for name, passed in pillars.items()))
    print(f"promote={all(pillars.values())} retire={failures >= 2} failures={failures}/5")
    print(f"reserved_holdout={HOLDOUT_START} onward NOT EVALUATED")


if __name__ == "__main__":
    main()
