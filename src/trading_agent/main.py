import argparse
from pathlib import Path

from trading_agent.research.continuous import evaluate_continuous_v3
from trading_agent.research.futures import (
    build_front_month_series,
    evaluate_futures_execution,
    load_futures_contracts,
)
from trading_agent.execution.futures_account import (
    FuturesChargeConfig, FuturesMarginConfig,
)

from trading_agent.core.config import (
    SelectorType,
    V1_CONFIG,
    V2_CONFIG,
)

from trading_agent.data.provider import (
    get_historical_market_data,
)

from trading_agent.research.experiment import (
    create_final_holdout_windows,
    create_walk_forward_windows,
    diagnose_v2_windows,
    evaluate_selector_system,
    evaluate_v2_system,
    split_development_and_holdout,
)


# =====================================================
# CLI
# =====================================================


def parse_arguments():

    parser = argparse.ArgumentParser(
        description=(
            "NSE Trading Agent - "
            "Deterministic V1"
        )
    )

    parser.add_argument(
        "--final-holdout",

        action="store_true",

        help=(
            "Legacy option retained for compatibility. "
            "The V1 final holdout is consumed and reruns are disabled."
        ),
    )

    return parser.parse_args()


# =====================================================
# Printing
# =====================================================


def print_v1_config():

    config = (
        V1_CONFIG
    )

    execution = (
        config.execution
    )

    print(
        "\n========================================"
    )

    print(
        "FROZEN DETERMINISTIC V1 CONFIG"
    )

    print(
        "========================================"
    )

    print(
        "Selector:",
        config.selector.value,
    )

    print(
        "Acceptance:"
    )

    print(
        "  Train P&L >",
        config.minimum_train_pnl,
    )

    print(
        "  Train trades >=",
        config.minimum_train_trades,
    )

    print(
        "Train window:",
        config.train_size,
    )

    print(
        "Test window:",
        config.test_size,
    )

    print(
        "Final holdout:",
        config.final_holdout_size,
        "candles",
    )

    print(
        "Initial capital:",
        execution.initial_capital,
    )

    print(
        "Position size:",
        execution.position_size,
    )

    print(
        "Transaction cost:",
        execution.transaction_cost,
    )

    print(
        "Slippage:",
        execution.slippage,
        "points",
    )

    print(
        "Force liquidation:",
        execution.force_liquidation,
    )


def print_summary(
    title,
    summary,
):

    print(
        "\n========================================"
    )

    print(
        title
    )

    print(
        "========================================"
    )

    print(
        "Selector:",
        summary.selector.value,
    )

    print(
        "Total windows:",
        summary.total_windows,
    )

    print(
        "Accepted windows:",
        summary.accepted_windows,
    )

    print(
        "Rejected windows:",
        summary.rejected_windows,
    )

    print(
        "\n--- STRATEGY ---"
    )

    print(
        "Total OOS P&L:",
        round(
            summary.total_oos_pnl,
            2,
        ),
    )

    print(
        "Average OOS P&L:",
        round(
            summary.average_oos_pnl,
            2,
        ),
    )

    print(
        "Average OOS return:",
        round(
            summary.average_oos_return,
            2,
        ),
        "%",
    )

    print(
        "Profitable windows:",
        summary.profitable_windows,
        "/",
        summary.accepted_windows,
    )

    print(
        "Profitable window rate:",
        round(
            summary.profitable_window_rate,
            2,
        ),
        "%",
    )

    print(
        "Total OOS trades:",
        summary.total_oos_trades,
    )

    print(
        "Average win rate:",
        round(
            summary.average_oos_win_rate,
            2,
        ),
        "%",
    )

    print(
        "\n--- RISK ---"
    )

    print(
        "Average strategy drawdown:",
        round(
            summary.average_strategy_drawdown,
            2,
        ),
    )

    print(
        "Average strategy P&L/DD:",
        round(
            summary.average_strategy_profit_dd,
            2,
        ),
    )

    print(
        "\n--- EXPOSURE ---"
    )

    print(
        "Average exposure:",
        round(
            summary.average_exposure_percent,
            2,
        ),
        "%",
    )

    print(
        "\n--- BENCHMARK ---"
    )

    print(
        "Benchmark total P&L:",
        round(
            summary.total_benchmark_pnl,
            2,
        ),
    )

    print(
        "Benchmark average return:",
        round(
            summary.average_benchmark_return,
            2,
        ),
        "%",
    )

    print(
        "Benchmark average drawdown:",
        round(
            summary.average_benchmark_drawdown,
            2,
        ),
    )

    print(
        "Benchmark average P&L/DD:",
        round(
            summary.average_benchmark_profit_dd,
            2,
        ),
    )

    print(
        "\n--- RELATIVE PERFORMANCE ---"
    )

    print(
        "Total excess P&L:",
        round(
            summary.total_excess_pnl,
            2,
        ),
    )

    print(
        "Average excess return:",
        round(
            summary.average_excess_return,
            2,
        ),
        "%",
    )

    print(
        "Benchmark beaten:",
        summary.benchmark_beaten_windows,
        "/",
        summary.accepted_windows,
    )

    print(
        "Benchmark beat rate:",
        round(
            summary.benchmark_beaten_rate,
            2,
        ),
        "%",
    )


# =====================================================
# Development comparison
# =====================================================


def run_development_comparison(
    development_data,
):

    windows = (
        create_walk_forward_windows(
            development_data,

            train_size=(
                V1_CONFIG.train_size
            ),

            test_size=(
                V1_CONFIG.test_size
            ),
        )
    )

    _, pnl_summary = (
        evaluate_selector_system(
            windows,
            V1_CONFIG,
            SelectorType.PNL,
        )
    )

    _, risk_summary = (
        evaluate_selector_system(
            windows,
            V1_CONFIG,
            SelectorType.RISK_ADJUSTED,
        )
    )

    print_summary(
        "DEVELOPMENT - P&L SELECTOR",
        pnl_summary,
    )

    print_summary(
        "DEVELOPMENT - RISK SELECTOR",
        risk_summary,
    )

    print(
        "\n========================================"
    )

    print(
        "DEVELOPMENT SELECTOR COMPARISON"
    )

    print(
        "========================================"
    )

    print(
        "Metric                 P&L          Risk"
    )

    print(
        "Accepted             ",
        pnl_summary.accepted_windows,
        "           ",
        risk_summary.accepted_windows,
    )

    print(
        "OOS P&L              ",
        round(
            pnl_summary.total_oos_pnl,
            2,
        ),
        "     ",
        round(
            risk_summary.total_oos_pnl,
            2,
        ),
    )

    print(
        "Benchmark P&L        ",
        round(
            pnl_summary.total_benchmark_pnl,
            2,
        ),
        "     ",
        round(
            risk_summary.total_benchmark_pnl,
            2,
        ),
    )

    print(
        "Excess P&L           ",
        round(
            pnl_summary.total_excess_pnl,
            2,
        ),
        "     ",
        round(
            risk_summary.total_excess_pnl,
            2,
        ),
    )

    print(
        "Benchmark beat %     ",
        round(
            pnl_summary.benchmark_beaten_rate,
            2,
        ),
        "        ",
        round(
            risk_summary.benchmark_beaten_rate,
            2,
        ),
    )

    print(
        "Exposure %           ",
        round(
            pnl_summary.average_exposure_percent,
            2,
        ),
        "        ",
        round(
            risk_summary.average_exposure_percent,
            2,
        ),
    )

    print(
        "Avg strategy DD      ",
        round(
            pnl_summary.average_strategy_drawdown,
            2,
        ),
        "     ",
        round(
            risk_summary.average_strategy_drawdown,
            2,
        ),
    )

    print(
        "Avg benchmark DD     ",
        round(
            pnl_summary.average_benchmark_drawdown,
            2,
        ),
        "     ",
        round(
            risk_summary.average_benchmark_drawdown,
            2,
        ),
    )

    v2_windows = create_walk_forward_windows(
        development_data,
        train_size=V2_CONFIG.train_size,
        test_size=V2_CONFIG.test_size,
    )
    v2_results, v2_summary = evaluate_v2_system(
        v2_windows,
        V2_CONFIG,
    )
    diagnostics = diagnose_v2_windows(v2_windows, V2_CONFIG)

    print_summary(
        "DEVELOPMENT - FROZEN V2 TREND-MOMENTUM",
        v2_summary,
    )

    print("\n========================================")
    print("V1 VS V2 DEVELOPMENT COMPARISON")
    print("========================================")
    print("Metric                    V1          V2")
    print("Accepted             ", risk_summary.accepted_windows,
          "          ", v2_summary.accepted_windows)
    print("OOS P&L              ", round(risk_summary.total_oos_pnl, 2),
          "     ", round(v2_summary.total_oos_pnl, 2))
    print("Total OOS trades     ", risk_summary.total_oos_trades,
          "          ", v2_summary.total_oos_trades)
    print("Exposure %           ", round(risk_summary.average_exposure_percent, 2),
          "       ", round(v2_summary.average_exposure_percent, 2))
    print("Benchmark beat %     ", round(risk_summary.benchmark_beaten_rate, 2),
          "       ", round(v2_summary.benchmark_beaten_rate, 2))

    print("\nV2 TRAINING DIAGNOSTICS")
    print("Windows:", len(diagnostics))
    print("Positive P&L:", sum(item.train_pnl > 0 for item in diagnostics))
    print("At least 5 completed trades:",
          sum(item.completed_trades >= 5 for item in diagnostics))
    print("Accepted:", sum(item.accepted for item in diagnostics))
    print("Training ATR stop signals:",
          sum(item.atr_stop_signals for item in diagnostics))
    print("Accepted OOS ATR stop signals:",
          sum(item.test_atr_stop_signals for item in v2_results))

    v3_result = evaluate_continuous_v3(development_data, V2_CONFIG)
    print("\n========================================")
    print("V3 STEP 1 - CONTINUOUS PORTFOLIO")
    print("========================================")
    print("Accepted windows:", v3_result.accepted_windows)
    print("Rejected windows:", v3_result.rejected_windows)
    print("Continuous P&L:", round(v3_result.total_pnl, 2))
    print("Continuous return:", round(v3_result.total_return, 2), "%")
    print("Completed trades:", len(v3_result.trades))
    print("Gate liquidations:", v3_result.gate_liquidations)
    print("Maximum drawdown:", round(v3_result.max_drawdown, 2))
    print("Exposure:", round(v3_result.exposure_percent, 2), "%")
    print("Continuous benchmark P&L:", round(v3_result.benchmark_pnl, 2))
    print("Excess P&L:", round(v3_result.excess_pnl, 2))

    futures = build_front_month_series(
        load_futures_contracts(Path("data/futures"), symbol=V2_CONFIG.symbol)
    )
    futures_result = evaluate_futures_execution(
        development_data, futures, V2_CONFIG
    )
    print("\n========================================")
    print("V3 STEP 2 - REAL NIFTY FUTURES EXECUTION")
    print("========================================")
    print("Accepted windows:", futures_result.accepted_windows)
    print("Rejected windows:", futures_result.rejected_windows)
    print("Starting capital:", round(V2_CONFIG.execution.initial_capital, 2))
    print("Final equity:", round(futures_result.final_equity, 2))
    print("Futures P&L:", round(futures_result.total_pnl, 2))
    print("Futures return:", round(futures_result.total_return, 2), "%")
    print("Strategy exits:", futures_result.strategy_trades)
    print("Gate liquidations:", futures_result.gate_liquidations)
    print("Contract rolls:", futures_result.rolls)
    print("Maximum drawdown:", round(futures_result.max_drawdown, 2))
    print("Exposure:", round(futures_result.exposure_percent, 2), "%")
    print("Missing futures sessions:", futures_result.missing_futures_dates)
    print("Continuous futures benchmark P&L:",
          round(futures_result.benchmark_pnl, 2))

    funded_result = evaluate_futures_execution(
        development_data, futures, V2_CONFIG, FuturesMarginConfig(),
        initial_capital=1_000_000,
        charge_config=FuturesChargeConfig(),
    )
    print("\n--- ₹10,00,000 CAPITAL + MARGIN + DATED LEVIES ---")
    print("Initial / maintenance margin:", "15% / 12%")
    print("Executed strategy exits:", funded_result.strategy_trades)
    print("Rejected entry attempts:", funded_result.rejected_entries)
    print("Margin calls:", funded_result.margin_calls)
    print("Final equity:", round(funded_result.final_equity, 2))
    print("Futures P&L:", round(funded_result.total_pnl, 2))
    print("Return:", round(funded_result.total_return, 2), "%")
    print("Total charges:", round(funded_result.total_charges, 2))
    print("Peak margin:", round(funded_result.peak_margin, 2))
    print("Minimum free cash:", round(funded_result.minimum_free_cash, 2))
    print("Benchmark entry rejected:", funded_result.benchmark_entry_rejected)
    print("Funded futures benchmark P&L:",
          round(funded_result.benchmark_pnl, 2))


# =====================================================
# FINAL HOLDOUT
# =====================================================


def run_final_holdout(
    development_data,
    holdout_data,
):

    print(
        "\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    )

    print(
        "FINAL HOLDOUT EVALUATION"
    )

    print(
        "Frozen selector:",
        V1_CONFIG.selector.value,
    )

    print(
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    )

    windows = (
        create_final_holdout_windows(
            development_data,
            holdout_data,

            train_size=(
                V1_CONFIG.train_size
            ),

            test_size=(
                V1_CONFIG.test_size
            ),
        )
    )

    _, summary = (
        evaluate_selector_system(
            windows,
            V1_CONFIG,
            V1_CONFIG.selector,
        )
    )

    print_summary(
        "V1 FINAL HOLDOUT RESULT",
        summary,
    )

    print(
        "\n========================================"
    )

    print(
        "V1 HOLDOUT HAS NOW BEEN CONSUMED"
    )

    print(
        "========================================"
    )

    print(
        "Do not tune V1 and rerun this "
        "holdout as a new unbiased test."
    )


# =====================================================
# Main
# =====================================================


def main():

    args = (
        parse_arguments()
    )

    market_data = (
        get_historical_market_data()
    )

    (
        development_data,
        holdout_data,
    ) = (
        split_development_and_holdout(
            market_data,

            V1_CONFIG.final_holdout_size,
        )
    )

    print(
        "Development:",
        development_data[
            0
        ].date.date(),
        "→",
        development_data[
            -1
        ].date.date(),
    )

    print(
        "Final holdout:",
        holdout_data[
            0
        ].date.date(),
        "→",
        holdout_data[
            -1
        ].date.date(),
    )

    print_v1_config()

    # =================================================
    # Development-only selector comparison
    # =================================================

    run_development_comparison(
        development_data
    )

    # =================================================
    # Holdout guard
    # =================================================

    print("\n========================================")
    print("V1 FINAL HOLDOUT: CONSUMED")
    print("========================================")
    print("Rerunning it as an unbiased evaluation is disabled.")

    if args.final_holdout:
        print("The --final-holdout request was refused.")


if __name__ == "__main__":
    main()
