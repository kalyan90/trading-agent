from pydantic import BaseModel

from trading_agent.backtest import (
    calculate_buy_price,
    calculate_profit_drawdown_ratio,
    calculate_sell_price,
    run_backtest,
)
from trading_agent.config import V2Config
from trading_agent.experiment import create_v2_trading_config
from trading_agent.features import build_market_features
from trading_agent.performance import calculate_max_drawdown
from trading_agent.strategy import Action, generate_trend_momentum_signal
from trading_agent.trade import Trade


class ContinuousResult(BaseModel):
    total_windows: int
    accepted_windows: int
    rejected_windows: int
    trades: list[Trade]
    final_equity: float
    total_pnl: float
    total_return: float
    max_drawdown: float
    exposure_percent: float
    gate_liquidations: int
    benchmark_pnl: float
    excess_pnl: float


def evaluate_continuous_v3(market_data, config: V2Config) -> ContinuousResult:
    """Run one continuous portfolio through chronological gated windows."""
    trading = create_v2_trading_config(config)
    start = config.train_size
    decisions = {}
    total_windows = 0

    while start + config.test_size <= len(market_data):
        train = market_data[start - config.train_size:start]
        result = run_backtest(train, trading, verbose=False)
        accepted = (
            result.total_pnl > config.minimum_train_pnl
            and len(result.trades) >= config.minimum_train_trades
        )
        decisions[start] = accepted
        total_windows += 1
        start += config.test_size

    if not decisions:
        raise ValueError("Not enough market data for a complete V3 window")

    cash = trading.initial_capital
    position = 0
    entry_price = 0.0
    entry_date = None
    entry_atr = None
    pending_action = None
    pending_atr = None
    trades = []
    equity_history = []
    exposed = 0
    eligible = 0
    gate_liquidations = 0
    allowed = False
    final_index = max(decisions) + config.test_size

    for index in range(config.train_size, final_index):
        market = market_data[index]

        if index in decisions:
            allowed = decisions[index]
            if not allowed and position:
                exit_price = calculate_sell_price(market.open, trading.slippage)
                cash += exit_price * position - trading.transaction_cost / 2
                trades.append(Trade(
                    entry_date=entry_date,
                    entry_price=entry_price,
                    exit_date=market.date,
                    exit_price=exit_price,
                    profit=exit_price - entry_price - trading.transaction_cost,
                ))
                position = 0
                entry_atr = None
                gate_liquidations += 1
            if not allowed:
                pending_action = None
                pending_atr = None

        eligible += 1
        if allowed:
            if pending_action == Action.BUY and position == 0:
                entry_price = calculate_buy_price(market.open, trading.slippage)
                cash -= entry_price + trading.transaction_cost / 2
                position = 1
                entry_date = market.date
                entry_atr = pending_atr
            elif pending_action == Action.SELL and position:
                exit_price = calculate_sell_price(market.open, trading.slippage)
                cash += exit_price - trading.transaction_cost / 2
                trades.append(Trade(
                    entry_date=entry_date,
                    entry_price=entry_price,
                    exit_date=market.date,
                    exit_price=exit_price,
                    profit=exit_price - entry_price - trading.transaction_cost,
                ))
                position = 0
                entry_atr = None

            features = build_market_features(
                market_data[:index + 1],
                fast_sma_period=trading.fast_sma_period,
                slow_sma_period=trading.slow_sma_period,
                rsi_period=trading.rsi_period,
                macd_fast_period=trading.macd_fast_period,
                macd_slow_period=trading.macd_slow_period,
                macd_signal_period=trading.macd_signal_period,
                atr_period=trading.atr_period,
            )
            signal = generate_trend_momentum_signal(features)
            if (
                position
                and entry_atr is not None
                and market.close <= entry_price - trading.atr_stop_multiple * entry_atr
            ):
                signal = signal.model_copy(update={"action": Action.SELL})
            pending_action = signal.action
            pending_atr = features.atr
        else:
            pending_action = None
            pending_atr = None

        if position:
            exposed += 1
        equity_history.append(cash + position * market.close)

    final_close = market_data[final_index - 1].close
    final_equity = cash + position * final_close
    total_pnl = final_equity - trading.initial_capital

    first_open = market_data[config.train_size].open
    benchmark_pnl = (
        final_close
        - calculate_buy_price(first_open, trading.slippage)
        - trading.transaction_cost / 2
    )

    return ContinuousResult(
        total_windows=total_windows,
        accepted_windows=sum(decisions.values()),
        rejected_windows=total_windows - sum(decisions.values()),
        trades=trades,
        final_equity=final_equity,
        total_pnl=total_pnl,
        total_return=total_pnl / trading.initial_capital * 100,
        max_drawdown=calculate_max_drawdown(equity_history),
        exposure_percent=exposed / eligible * 100,
        gate_liquidations=gate_liquidations,
        benchmark_pnl=benchmark_pnl,
        excess_pnl=total_pnl - benchmark_pnl,
    )
