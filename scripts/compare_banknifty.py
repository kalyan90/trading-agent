"""Development-only BANKNIFTY comparison with a reserved 250-session holdout."""

from pathlib import Path

from trading_agent.core.config import V2_CONFIG
from trading_agent.data.index import load_index_history
from trading_agent.execution.futures_account import FuturesChargeConfig, FuturesMarginConfig
from trading_agent.research.continuous import evaluate_continuous_v3
from trading_agent.research.experiment import create_walk_forward_windows, evaluate_v2_system
from trading_agent.research.futures import (
    build_front_month_series, evaluate_futures_execution, load_futures_contracts,
)


def main():
    all_spot = load_index_history(Path("data/index"), "NIFTY BANK")
    development, holdout = all_spot[:-250], all_spot[-250:]
    config = V2_CONFIG.model_copy(update={"symbol": "BANKNIFTY"})
    windows = create_walk_forward_windows(
        development, train_size=config.train_size, test_size=config.test_size
    )
    _, reset = evaluate_v2_system(windows, config)
    continuous = evaluate_continuous_v3(development, config)
    futures = build_front_month_series(load_futures_contracts(
        Path("data/futures"), symbol="BANKNIFTY"
    ))
    funded = evaluate_futures_execution(
        development, futures, config, FuturesMarginConfig(),
        initial_capital=1_000_000, charge_config=FuturesChargeConfig(),
    )
    print(f"Development: {development[0].date.date()} -> {development[-1].date.date()}")
    print(f"Reserved holdout: {holdout[0].date.date()} -> {holdout[-1].date.date()}")
    print("BANKNIFTY V2 RESET-WINDOW")
    print(f"windows={reset.total_windows} accepted={reset.accepted_windows}")
    print(f"pnl={reset.total_oos_pnl:.2f} trades={reset.total_oos_trades}")
    print(f"benchmark={reset.total_benchmark_pnl:.2f} excess={reset.total_excess_pnl:.2f}")
    print("BANKNIFTY V3 CONTINUOUS SPOT")
    print(f"pnl={continuous.total_pnl:.2f} return={continuous.total_return:.2f}%")
    print(f"drawdown={continuous.max_drawdown:.2f} exposure={continuous.exposure_percent:.2f}%")
    print(f"benchmark={continuous.benchmark_pnl:.2f} excess={continuous.excess_pnl:.2f}")
    print("BANKNIFTY V3 FUNDED FUTURES")
    print(f"pnl={funded.total_pnl:.2f} return={funded.total_return:.2f}%")
    print(f"trades={funded.strategy_trades} rolls={funded.rolls}")
    print(f"drawdown={funded.max_drawdown:.2f} exposure={funded.exposure_percent:.2f}%")
    print(f"charges={funded.total_charges:.2f} peak_margin={funded.peak_margin:.2f}")
    print(f"benchmark={funded.benchmark_pnl:.2f} rejected={funded.rejected_entries}")
    print(f"minimum_free_cash={funded.minimum_free_cash:.2f} margin_calls={funded.margin_calls}")
    print(f"missing_futures_sessions={funded.missing_futures_dates}")


if __name__ == "__main__":
    main()
