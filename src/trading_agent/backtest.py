from trading_agent.config import (
    StrategyType,
)

from trading_agent.indicators import (
    calculate_sma,
)

from trading_agent.features import build_market_features

from trading_agent.performance import (
    calculate_average_profit,
    calculate_max_drawdown,
    calculate_win_loss,
    calculate_win_rate,
)

from trading_agent.portfolio import Portfolio

from trading_agent.strategy import (
    Action,
    generate_crossover_signal,
    generate_sma_signal,
    generate_trend_momentum_signal,
)

from trading_agent.trade import (
    BacktestResult,
    Trade,
)


# =====================================================
# Execution helpers
# =====================================================


def calculate_buy_price(
    market_price: float,
    slippage: float,
) -> float:
    """
    A BUY suffers adverse slippage upward.
    """

    return (
        market_price
        + slippage
    )


def calculate_sell_price(
    market_price: float,
    slippage: float,
) -> float:
    """
    A SELL suffers adverse slippage downward.
    """

    return (
        market_price
        - slippage
    )


def calculate_profit_drawdown_ratio(
    pnl: float,
    max_drawdown: float,
) -> float:
    """
    Simple risk-adjusted metric used by V1.

    We deliberately keep this simple instead of
    introducing Sharpe/Sortino/etc. in V1.
    """

    if max_drawdown <= 0:
        return 0

    return (
        pnl
        / max_drawdown
    )


# =====================================================
# Benchmark
# =====================================================


def calculate_buy_and_hold_benchmark(
    market_data,
    config,
    benchmark_start_index: int,
) -> tuple[
    float,
    float,
    float,
    float,
]:
    """
    Conditional buy-and-hold benchmark.

    Buy:
        first trade-eligible OOS OPEN.

    Hold:
        through the same OOS evaluation window.

    End:
        mark to market at final CLOSE unless
        force_liquidation=True.

    Returns:
        benchmark_pnl
        benchmark_return
        benchmark_max_drawdown
        benchmark_profit_drawdown_ratio
    """

    if benchmark_start_index >= len(
        market_data
    ):
        return (
            0,
            0,
            0,
            0,
        )

    quantity = (
        config.max_position_size
    )

    first_market = (
        market_data[
            benchmark_start_index
        ]
    )

    entry_price = (
        calculate_buy_price(
            first_market.open,
            config.slippage,
        )
    )

    cash = (
        config.initial_capital
        - (
            entry_price
            * quantity
        )
        - (
            config.transaction_cost
            / 2
        )
    )

    equity_history = []

    # -------------------------------------------------
    # Mark benchmark to market each candle.
    # -------------------------------------------------

    for market in market_data[
        benchmark_start_index:
    ]:

        equity = (
            cash
            + (
                market.close
                * quantity
            )
        )

        equity_history.append(
            equity
        )

    final_market = (
        market_data[-1]
    )

    # -------------------------------------------------
    # Optional explicit liquidation.
    # -------------------------------------------------

    if config.force_liquidation:

        exit_price = (
            calculate_sell_price(
                final_market.close,
                config.slippage,
            )
        )

        final_equity = (
            cash
            + (
                exit_price
                * quantity
            )
            - (
                config.transaction_cost
                / 2
            )
        )

        equity_history.append(
            final_equity
        )

    else:

        final_equity = (
            cash
            + (
                final_market.close
                * quantity
            )
        )

    benchmark_pnl = (
        final_equity
        - config.initial_capital
    )

    benchmark_return = (
        benchmark_pnl
        / config.initial_capital
    ) * 100

    benchmark_max_drawdown = (
        calculate_max_drawdown(
            equity_history
        )
        if equity_history
        else 0
    )

    benchmark_profit_drawdown_ratio = (
        calculate_profit_drawdown_ratio(
            benchmark_pnl,
            benchmark_max_drawdown,
        )
    )

    return (
        benchmark_pnl,
        benchmark_return,
        benchmark_max_drawdown,
        benchmark_profit_drawdown_ratio,
    )


# =====================================================
# Backtester
# =====================================================


def run_backtest(
    market_data,
    config,
    trade_start_index: int = 0,
    verbose: bool = True,
) -> BacktestResult:

    portfolio = Portfolio(
        initial_capital=(
            config.initial_capital
        ),
        cash=(
            config.initial_capital
        ),
    )

    entry_price = 0
    entry_date = None

    # A close signal executes at the next OPEN.
    pending_action = None
    pending_atr = None
    entry_atr = None

    total_profit = 0

    trades = []

    buy_signals = 0
    sell_signals = 0
    hold_signals = 0
    entries = 0
    exits = 0
    atr_stop_signals = 0

    equity_history = []

    prices = [
        market.close
        for market in market_data
    ]

    total_exposure_bars = 0
    invested_bars = 0

    warmup_period = (
        config.slow_sma_period
        if config.strategy == StrategyType.TREND_MOMENTUM
        else config.sma_period
    )

    benchmark_start_index = max(
        trade_start_index,
        warmup_period,
        1,
    )

    # =================================================
    # Main candle loop
    # =================================================

    for i in range(
        1,
        len(market_data),
    ):

        market = market_data[i]

        previous_market = (
            market_data[
                i - 1
            ]
        )

        # ---------------------------------------------
        # Indicator warm-up
        # ---------------------------------------------

        if i < warmup_period:
            continue

        previous_sma = None
        if config.strategy != StrategyType.TREND_MOMENTUM:
            previous_sma = calculate_sma(
                prices[:i], config.sma_period
            )

        # ---------------------------------------------
        # Do not trade inside training warm-up candles.
        # ---------------------------------------------

        if i < trade_start_index:
            continue

        total_exposure_bars += 1

        # =============================================
        # STEP 1:
        # Execute yesterday's signal at today's OPEN.
        # =============================================

        if (
            pending_action
            == Action.BUY

            and

            portfolio.position
            == 0
        ):

            quantity = (
                config.max_position_size
            )

            execution_price = (
                calculate_buy_price(
                    market.open,
                    config.slippage,
                )
            )

            portfolio.buy(
                execution_price,
                quantity,
                config.transaction_cost
                / 2,
            )
            entries += 1

            entry_price = (
                execution_price
            )

            entry_date = (
                market.date
            )
            entry_atr = pending_atr

            if verbose:
                print(
                    "BUY:",
                    market.date,
                    "Market:",
                    market.open,
                    "Execution:",
                    execution_price,
                    "Quantity:",
                    quantity,
                )

        elif (
            pending_action
            == Action.SELL

            and

            portfolio.position
            > 0
        ):

            quantity = (
                portfolio.position
            )

            execution_price = (
                calculate_sell_price(
                    market.open,
                    config.slippage,
                )
            )

            gross_profit = (
                (
                    execution_price
                    - entry_price
                )
                * quantity
            )

            net_profit = (
                gross_profit
                - config.transaction_cost
            )

            trade = Trade(
                entry_date=entry_date,
                entry_price=entry_price,

                exit_date=market.date,
                exit_price=execution_price,

                profit=net_profit,
            )

            trades.append(
                trade
            )

            total_profit += (
                net_profit
            )

            portfolio.sell(
                execution_price,
                quantity,
                config.transaction_cost
                / 2,
            )
            exits += 1

            if verbose:
                print(
                    "SELL:",
                    market.date,
                    "Market:",
                    market.open,
                    "Execution:",
                    execution_price,
                    "Quantity:",
                    quantity,
                    "Profit:",
                    net_profit,
                )

            entry_price = 0
            entry_date = None
            entry_atr = None

        pending_action = None
        pending_atr = None

        # =============================================
        # Exposure
        # =============================================

        if portfolio.position > 0:
            invested_bars += 1

        # =============================================
        # STEP 2:
        # Calculate today's indicator using only
        # information available through today's CLOSE.
        # =============================================

        sma = None
        if config.strategy != StrategyType.TREND_MOMENTUM:
            sma = calculate_sma(
                prices[: i + 1], config.sma_period
            )

        # =============================================
        # STEP 3:
        # Generate today's signal.
        # =============================================

        if (
            config.strategy
            == StrategyType.SMA_BASIC
        ):

            signal = (
                generate_sma_signal(
                    market.close,
                    sma,
                )
            )

        elif (
            config.strategy
            == StrategyType.SMA_CROSSOVER
        ):

            signal = (
                generate_crossover_signal(
                    previous_market.close,
                    previous_sma,

                    market.close,
                    sma,
                )
            )

        elif config.strategy == StrategyType.TREND_MOMENTUM:
            features = build_market_features(
                market_data[: i + 1],
                fast_sma_period=config.fast_sma_period,
                slow_sma_period=config.slow_sma_period,
                rsi_period=config.rsi_period,
                macd_fast_period=config.macd_fast_period,
                macd_slow_period=config.macd_slow_period,
                macd_signal_period=config.macd_signal_period,
                atr_period=config.atr_period,
            )
            signal = generate_trend_momentum_signal(features)

            stop_price = (
                entry_price
                - config.atr_stop_multiple * entry_atr
                if entry_atr is not None
                else None
            )
            if (
                portfolio.position > 0
                and stop_price is not None
                and market.close <= stop_price
            ):
                signal = signal.model_copy(update={
                    "action": Action.SELL,
                    "confidence": 1,
                    "reason": "ATR risk stop",
                })
                atr_stop_signals += 1

        else:

            raise ValueError(
                "Unsupported strategy: "
                f"{config.strategy}"
            )

        if verbose:
            print(
                "SIGNAL:",
                market.date,
                "Close:",
                market.close,
                "SMA:",
                sma,
                "Action:",
                signal.action,
            )

        # Signal waits until next OPEN.
        pending_action = (
            signal.action
        )
        if config.strategy == StrategyType.TREND_MOMENTUM:
            pending_atr = features.atr

        if signal.action == Action.BUY:
            buy_signals += 1
        elif signal.action == Action.SELL:
            sell_signals += 1
        else:
            hold_signals += 1

        # =============================================
        # STEP 4:
        # Mark portfolio to market.
        # =============================================

        current_equity = (
            portfolio.equity(
                market.close
            )
        )

        equity_history.append(
            current_equity
        )

    # =================================================
    # End-of-window accounting
    # =================================================

    final_market = (
        market_data[-1]
    )

    if (
        config.force_liquidation

        and

        portfolio.position > 0
    ):

        quantity = (
            portfolio.position
        )

        execution_price = (
            calculate_sell_price(
                final_market.close,
                config.slippage,
            )
        )

        gross_profit = (
            (
                execution_price
                - entry_price
            )
            * quantity
        )

        net_profit = (
            gross_profit
            - config.transaction_cost
        )

        trade = Trade(
            entry_date=entry_date,
            entry_price=entry_price,

            exit_date=final_market.date,
            exit_price=execution_price,

            profit=net_profit,
        )

        trades.append(
            trade
        )

        total_profit += (
            net_profit
        )

        portfolio.sell(
            execution_price,
            quantity,
            config.transaction_cost
            / 2,
        )
        exits += 1

        equity_history.append(
            portfolio.equity(
                final_market.close
            )
        )

        if verbose:
            print(
                "FORCED SELL:",
                final_market.date,
                "Execution:",
                execution_price,
                "Quantity:",
                quantity,
                "Profit:",
                net_profit,
            )

    # =================================================
    # Strategy performance
    # =================================================

    (
        winning_trades,
        losing_trades,
    ) = calculate_win_loss(
        trades
    )

    win_rate = calculate_win_rate(
        len(trades),
        winning_trades,
    )

    average_profit = (
        calculate_average_profit(
            total_profit,
            len(trades),
        )
    )

    max_drawdown = (
        calculate_max_drawdown(
            equity_history
        )
        if equity_history
        else 0
    )

    final_equity = (
        portfolio.equity(
            final_market.close
        )
    )

    total_pnl = (
        final_equity
        - portfolio.initial_capital
    )

    total_return = (
        total_pnl
        / portfolio.initial_capital
    ) * 100

    profit_drawdown_ratio = (
        calculate_profit_drawdown_ratio(
            total_pnl,
            max_drawdown,
        )
    )

    # =================================================
    # Exposure
    # =================================================

    exposure_percent = (
        (
            invested_bars
            / total_exposure_bars
        )
        * 100

        if total_exposure_bars > 0

        else 0
    )

    # =================================================
    # Benchmark
    # =================================================

    (
        benchmark_pnl,
        benchmark_return,
        benchmark_max_drawdown,
        benchmark_profit_drawdown_ratio,
    ) = (
        calculate_buy_and_hold_benchmark(
            market_data,
            config,
            benchmark_start_index,
        )
    )

    # =================================================
    # Relative performance
    # =================================================

    excess_pnl = (
        total_pnl
        - benchmark_pnl
    )

    excess_return = (
        total_return
        - benchmark_return
    )

    return BacktestResult(
        trades=trades,

        buy_signals=buy_signals,
        sell_signals=sell_signals,
        hold_signals=hold_signals,
        entries=entries,
        exits=exits,
        atr_stop_signals=atr_stop_signals,

        total_profit=total_profit,
        total_pnl=total_pnl,

        winning_trades=(
            winning_trades
        ),

        losing_trades=(
            losing_trades
        ),

        win_rate=win_rate,

        average_profit=(
            average_profit
        ),

        max_drawdown=(
            max_drawdown
        ),

        final_equity=(
            final_equity
        ),

        total_return=(
            total_return
        ),

        profit_drawdown_ratio=(
            profit_drawdown_ratio
        ),

        exposure_percent=(
            exposure_percent
        ),

        benchmark_pnl=(
            benchmark_pnl
        ),

        benchmark_return=(
            benchmark_return
        ),

        benchmark_max_drawdown=(
            benchmark_max_drawdown
        ),

        benchmark_profit_drawdown_ratio=(
            benchmark_profit_drawdown_ratio
        ),

        excess_pnl=(
            excess_pnl
        ),

        excess_return=(
            excess_return
        ),
    )
