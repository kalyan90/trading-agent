from pydantic import BaseModel

from trading_agent.backtest import (
    run_backtest,
)

from trading_agent.config import (
    SelectorType,
    StrategyType,
    TradingConfig,
    V1Config,
)


# =====================================================
# Models
# =====================================================


class ExperimentResult(BaseModel):
    strategy: StrategyType

    sma_period: int

    total_trades: int

    win_rate: float

    total_profit: float
    total_pnl: float

    max_drawdown: float

    profit_drawdown_ratio: float


class WalkForwardResult(BaseModel):
    window: int

    selector: SelectorType

    strategy: StrategyType

    sma_period: int

    # -------------------------------------------------
    # Training
    # -------------------------------------------------

    train_pnl: float
    train_trades: int
    train_win_rate: float
    train_drawdown: float
    train_profit_drawdown_ratio: float

    # -------------------------------------------------
    # OOS strategy
    # -------------------------------------------------

    test_profit: float
    test_pnl: float

    test_trades: int
    test_win_rate: float

    test_drawdown: float

    test_final_equity: float
    test_return: float

    test_profit_drawdown_ratio: float

    # -------------------------------------------------
    # Exposure
    # -------------------------------------------------

    test_exposure_percent: float

    # -------------------------------------------------
    # Benchmark
    # -------------------------------------------------

    benchmark_pnl: float
    benchmark_return: float

    benchmark_max_drawdown: float

    benchmark_profit_drawdown_ratio: float

    # -------------------------------------------------
    # Relative
    # -------------------------------------------------

    excess_pnl: float
    excess_return: float


class SystemSummary(BaseModel):
    selector: SelectorType

    total_windows: int

    accepted_windows: int
    rejected_windows: int

    profitable_windows: int
    losing_windows: int

    total_oos_pnl: float
    average_oos_pnl: float
    average_oos_return: float

    profitable_window_rate: float

    total_oos_trades: int
    average_oos_win_rate: float

    # -------------------------------------------------
    # Risk
    # -------------------------------------------------

    average_strategy_drawdown: float

    average_strategy_profit_dd: float

    # -------------------------------------------------
    # Exposure
    # -------------------------------------------------

    average_exposure_percent: float

    # -------------------------------------------------
    # Benchmark
    # -------------------------------------------------

    total_benchmark_pnl: float

    average_benchmark_return: float

    average_benchmark_drawdown: float

    average_benchmark_profit_dd: float

    # -------------------------------------------------
    # Relative
    # -------------------------------------------------

    total_excess_pnl: float

    average_excess_return: float

    benchmark_beaten_windows: int

    benchmark_beaten_rate: float


# =====================================================
# Dataset splitting
# =====================================================


def split_development_and_holdout(
    market_data,
    holdout_size: int,
):

    if holdout_size <= 0:
        raise ValueError(
            "holdout_size must be greater than 0"
        )

    if holdout_size >= len(
        market_data
    ):
        raise ValueError(
            "holdout_size must be smaller "
            "than market data size"
        )

    return (
        market_data[:-holdout_size],
        market_data[-holdout_size:],
    )


# =====================================================
# Development walk-forward windows
# =====================================================


def create_walk_forward_windows(
    market_data,
    train_size: int,
    test_size: int,
):

    windows = []

    start = 0

    while (
        start
        + train_size
        + test_size
        <= len(market_data)
    ):

        train_start = (
            start
        )

        train_end = (
            train_start
            + train_size
        )

        test_end = (
            train_end
            + test_size
        )

        train_data = (
            market_data[
                train_start:train_end
            ]
        )

        test_data = (
            market_data[
                train_end:test_end
            ]
        )

        windows.append(
            (
                train_data,
                test_data,
            )
        )

        # Test windows do not overlap.
        start += (
            test_size
        )

    return windows


# =====================================================
# Final holdout windows
# =====================================================


def create_final_holdout_windows(
    development_data,
    holdout_data,
    train_size: int,
    test_size: int,
):
    """
    Walk through the holdout chronologically.

    Each test window sees only the preceding
    train_size candles.

    Later holdout windows may use earlier holdout
    candles as historical training information,
    exactly as a real rolling system could.

    Future candles are never used.
    """

    if len(development_data) < train_size:
        raise ValueError(
            "Not enough development data "
            "for final holdout training"
        )

    combined_data = (
        development_data
        + holdout_data
    )

    holdout_start = (
        len(development_data)
    )

    windows = []

    test_start = (
        holdout_start
    )

    while test_start < len(
        combined_data
    ):

        test_end = min(
            test_start
            + test_size,

            len(combined_data),
        )

        train_start = (
            test_start
            - train_size
        )

        train_data = (
            combined_data[
                train_start:test_start
            ]
        )

        test_data = (
            combined_data[
                test_start:test_end
            ]
        )

        windows.append(
            (
                train_data,
                test_data,
            )
        )

        test_start = (
            test_end
        )

    return windows


# =====================================================
# Config conversion
# =====================================================


def create_trading_config(
    v1_config: V1Config,
    sma_period: int,
    strategy: StrategyType,
) -> TradingConfig:

    execution = (
        v1_config.execution
    )

    return TradingConfig(
        symbol=(
            v1_config.symbol
        ),

        minimum_confidence=(
            v1_config.minimum_confidence
        ),

        max_position_size=(
            execution.position_size
        ),

        initial_capital=(
            execution.initial_capital
        ),

        transaction_cost=(
            execution.transaction_cost
        ),

        slippage=(
            execution.slippage
        ),

        force_liquidation=(
            execution.force_liquidation
        ),

        sma_period=(
            sma_period
        ),

        strategy=(
            strategy
        ),
    )


# =====================================================
# Candidate training
# =====================================================


def run_experiments(
    market_data,
    v1_config: V1Config,
) -> list[ExperimentResult]:

    results = []

    for strategy in (
        v1_config.candidate_strategies
    ):

        for sma_period in (
            v1_config.candidate_sma_periods
        ):

            config = (
                create_trading_config(
                    v1_config,
                    sma_period,
                    strategy,
                )
            )

            result = (
                run_backtest(
                    market_data,
                    config,
                    verbose=False,
                )
            )

            results.append(
                ExperimentResult(
                    strategy=strategy,

                    sma_period=sma_period,

                    total_trades=len(
                        result.trades
                    ),

                    win_rate=(
                        result.win_rate
                    ),

                    total_profit=(
                        result.total_profit
                    ),

                    total_pnl=(
                        result.total_pnl
                    ),

                    max_drawdown=(
                        result.max_drawdown
                    ),

                    profit_drawdown_ratio=(
                        result.profit_drawdown_ratio
                    ),
                )
            )

    return results


# =====================================================
# Selector
# =====================================================


def select_candidate(
    results: list[ExperimentResult],
    selector: SelectorType,
) -> ExperimentResult:

    if selector == SelectorType.PNL:

        return max(
            results,
            key=lambda result: (
                result.total_pnl
            ),
        )

    if (
        selector
        == SelectorType.RISK_ADJUSTED
    ):

        return max(
            results,
            key=lambda result: (
                result.profit_drawdown_ratio
            ),
        )

    raise ValueError(
        f"Unsupported selector: {selector}"
    )


# =====================================================
# Frozen V1 acceptance gate
# =====================================================


def is_acceptable_result(
    result: ExperimentResult,
    v1_config: V1Config,
) -> bool:

    return (
        result.total_pnl
        > v1_config.minimum_train_pnl

        and

        result.total_trades
        >= v1_config.minimum_train_trades
    )


# =====================================================
# OOS execution
# =====================================================


def run_oos_experiment(
    selected_result: ExperimentResult,
    train_data,
    test_data,
    v1_config: V1Config,
):

    config = (
        create_trading_config(
            v1_config,

            selected_result.sma_period,

            selected_result.strategy,
        )
    )

    warmup_size = (
        config.sma_period
    )

    warmup_data = (
        train_data[
            -warmup_size:
        ]
    )

    test_market_data = (
        warmup_data
        + test_data
    )

    return run_backtest(
        test_market_data,
        config,

        trade_start_index=(
            warmup_size
        ),

        verbose=False,
    )


# =====================================================
# Build one structured window result
# =====================================================


def create_window_result(
    window_number: int,

    selector: SelectorType,

    selected_result: ExperimentResult,

    test_result,
) -> WalkForwardResult:

    return WalkForwardResult(
        window=(
            window_number
        ),

        selector=(
            selector
        ),

        strategy=(
            selected_result.strategy
        ),

        sma_period=(
            selected_result.sma_period
        ),

        # ---------------------------------------------
        # Training
        # ---------------------------------------------

        train_pnl=(
            selected_result.total_pnl
        ),

        train_trades=(
            selected_result.total_trades
        ),

        train_win_rate=(
            selected_result.win_rate
        ),

        train_drawdown=(
            selected_result.max_drawdown
        ),

        train_profit_drawdown_ratio=(
            selected_result.profit_drawdown_ratio
        ),

        # ---------------------------------------------
        # OOS
        # ---------------------------------------------

        test_profit=(
            test_result.total_profit
        ),

        test_pnl=(
            test_result.total_pnl
        ),

        test_trades=len(
            test_result.trades
        ),

        test_win_rate=(
            test_result.win_rate
        ),

        test_drawdown=(
            test_result.max_drawdown
        ),

        test_final_equity=(
            test_result.final_equity
        ),

        test_return=(
            test_result.total_return
        ),

        test_profit_drawdown_ratio=(
            test_result.profit_drawdown_ratio
        ),

        # ---------------------------------------------
        # Exposure
        # ---------------------------------------------

        test_exposure_percent=(
            test_result.exposure_percent
        ),

        # ---------------------------------------------
        # Benchmark
        # ---------------------------------------------

        benchmark_pnl=(
            test_result.benchmark_pnl
        ),

        benchmark_return=(
            test_result.benchmark_return
        ),

        benchmark_max_drawdown=(
            test_result.benchmark_max_drawdown
        ),

        benchmark_profit_drawdown_ratio=(
            test_result.benchmark_profit_drawdown_ratio
        ),

        # ---------------------------------------------
        # Relative
        # ---------------------------------------------

        excess_pnl=(
            test_result.excess_pnl
        ),

        excess_return=(
            test_result.excess_return
        ),
    )


# =====================================================
# Run a complete selector system
# =====================================================


def evaluate_selector_system(
    windows,

    v1_config: V1Config,

    selector: SelectorType,
) -> tuple[
    list[WalkForwardResult],
    SystemSummary,
]:

    window_results = []

    total_windows = len(
        windows
    )

    for index, (
        train_data,
        test_data,
    ) in enumerate(
        windows,
        start=1,
    ):

        training_results = (
            run_experiments(
                train_data,
                v1_config,
            )
        )

        selected_result = (
            select_candidate(
                training_results,
                selector,
            )
        )

        # ---------------------------------------------
        # Frozen baseline acceptance policy.
        # ---------------------------------------------

        if not is_acceptable_result(
            selected_result,
            v1_config,
        ):
            continue

        test_result = (
            run_oos_experiment(
                selected_result,
                train_data,
                test_data,
                v1_config,
            )
        )

        window_result = (
            create_window_result(
                index,
                selector,
                selected_result,
                test_result,
            )
        )

        window_results.append(
            window_result
        )

    summary = summarize_system(
        window_results,
        total_windows,
        selector,
    )

    return (
        window_results,
        summary,
    )


# =====================================================
# Summary
# =====================================================


def summarize_system(
    results: list[WalkForwardResult],

    total_windows: int,

    selector: SelectorType,
) -> SystemSummary:

    accepted_windows = (
        len(results)
    )

    rejected_windows = (
        total_windows
        - accepted_windows
    )

    if not results:

        return SystemSummary(
            selector=selector,

            total_windows=(
                total_windows
            ),

            accepted_windows=0,

            rejected_windows=(
                rejected_windows
            ),

            profitable_windows=0,
            losing_windows=0,

            total_oos_pnl=0,
            average_oos_pnl=0,
            average_oos_return=0,

            profitable_window_rate=0,

            total_oos_trades=0,
            average_oos_win_rate=0,

            average_strategy_drawdown=0,

            average_strategy_profit_dd=0,

            average_exposure_percent=0,

            total_benchmark_pnl=0,

            average_benchmark_return=0,

            average_benchmark_drawdown=0,

            average_benchmark_profit_dd=0,

            total_excess_pnl=0,

            average_excess_return=0,

            benchmark_beaten_windows=0,

            benchmark_beaten_rate=0,
        )

    # =================================================
    # Strategy
    # =================================================

    profitable_windows = sum(
        1
        for result in results
        if result.test_pnl > 0
    )

    losing_windows = sum(
        1
        for result in results
        if result.test_pnl < 0
    )

    total_oos_pnl = sum(
        result.test_pnl
        for result in results
    )

    average_oos_pnl = (
        total_oos_pnl
        / accepted_windows
    )

    average_oos_return = (
        sum(
            result.test_return
            for result in results
        )
        / accepted_windows
    )

    profitable_window_rate = (
        profitable_windows
        / accepted_windows
    ) * 100

    total_oos_trades = sum(
        result.test_trades
        for result in results
    )

    average_oos_win_rate = (
        sum(
            result.test_win_rate
            for result in results
        )
        / accepted_windows
    )

    # =================================================
    # Risk
    # =================================================

    average_strategy_drawdown = (
        sum(
            result.test_drawdown
            for result in results
        )
        / accepted_windows
    )

    average_strategy_profit_dd = (
        sum(
            result.test_profit_drawdown_ratio
            for result in results
        )
        / accepted_windows
    )

    # =================================================
    # Exposure
    # =================================================

    average_exposure_percent = (
        sum(
            result.test_exposure_percent
            for result in results
        )
        / accepted_windows
    )

    # =================================================
    # Benchmark
    # =================================================

    total_benchmark_pnl = sum(
        result.benchmark_pnl
        for result in results
    )

    average_benchmark_return = (
        sum(
            result.benchmark_return
            for result in results
        )
        / accepted_windows
    )

    average_benchmark_drawdown = (
        sum(
            result.benchmark_max_drawdown
            for result in results
        )
        / accepted_windows
    )

    average_benchmark_profit_dd = (
        sum(
            result.benchmark_profit_drawdown_ratio
            for result in results
        )
        / accepted_windows
    )

    # =================================================
    # Relative
    # =================================================

    total_excess_pnl = sum(
        result.excess_pnl
        for result in results
    )

    average_excess_return = (
        sum(
            result.excess_return
            for result in results
        )
        / accepted_windows
    )

    benchmark_beaten_windows = sum(
        1
        for result in results
        if result.excess_pnl > 0
    )

    benchmark_beaten_rate = (
        benchmark_beaten_windows
        / accepted_windows
    ) * 100

    return SystemSummary(
        selector=(
            selector
        ),

        total_windows=(
            total_windows
        ),

        accepted_windows=(
            accepted_windows
        ),

        rejected_windows=(
            rejected_windows
        ),

        profitable_windows=(
            profitable_windows
        ),

        losing_windows=(
            losing_windows
        ),

        total_oos_pnl=(
            total_oos_pnl
        ),

        average_oos_pnl=(
            average_oos_pnl
        ),

        average_oos_return=(
            average_oos_return
        ),

        profitable_window_rate=(
            profitable_window_rate
        ),

        total_oos_trades=(
            total_oos_trades
        ),

        average_oos_win_rate=(
            average_oos_win_rate
        ),

        average_strategy_drawdown=(
            average_strategy_drawdown
        ),

        average_strategy_profit_dd=(
            average_strategy_profit_dd
        ),

        average_exposure_percent=(
            average_exposure_percent
        ),

        total_benchmark_pnl=(
            total_benchmark_pnl
        ),

        average_benchmark_return=(
            average_benchmark_return
        ),

        average_benchmark_drawdown=(
            average_benchmark_drawdown
        ),

        average_benchmark_profit_dd=(
            average_benchmark_profit_dd
        ),

        total_excess_pnl=(
            total_excess_pnl
        ),

        average_excess_return=(
            average_excess_return
        ),

        benchmark_beaten_windows=(
            benchmark_beaten_windows
        ),

        benchmark_beaten_rate=(
            benchmark_beaten_rate
        ),
    )