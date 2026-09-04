"""Chronological shared-capital cash-equity portfolio research."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import sqrt
from statistics import mean, median, pstdev

from pydantic import BaseModel, ConfigDict

from trading_agent.core.config import ExecutionConfig, V2Config
from trading_agent.core.equity import EquityInstrument, EquityPortfolioConfig
from trading_agent.research.backtest import run_backtest
from trading_agent.research.experiment import create_v2_trading_config
from trading_agent.research.performance import calculate_max_drawdown
from trading_agent.signals.features import build_market_features
from trading_agent.signals.strategy import Action, generate_trend_momentum_signal


class EquityPortfolioResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbols: tuple[str, ...]
    first_development_date: date
    last_development_date: date
    reserved_holdout_start: date
    sessions: int
    total_pnl: float
    total_return: float
    max_drawdown: float
    annualized_sharpe: float
    completed_trades: int
    win_rate: float
    exposure_percent: float
    turnover: float
    transaction_costs: float
    rejected_orders: int
    accepted_symbol_windows: int
    total_symbol_windows: int
    benchmark_pnl: float
    excess_pnl: float
    yearly_pnl: dict[int, float]
    survivorship_bias_warning: bool


def _aligned_rows(data_by_symbol):
    common_dates = None
    by_symbol = {}
    for symbol, rows in data_by_symbol.items():
        date_map = {row.date.date(): row for row in rows}
        by_symbol[symbol] = date_map
        common_dates = set(date_map) if common_dates is None else common_dates & set(date_map)
    dates = sorted(common_dates or ())
    return dates, {
        symbol: [date_map[day] for day in dates]
        for symbol, date_map in by_symbol.items()
    }


def _sharpe(equity):
    returns = [current / previous - 1 for previous, current in zip(equity, equity[1:])
               if previous]
    volatility = pstdev(returns) if len(returns) > 1 else 0
    return mean(returns) / volatility * sqrt(252) if volatility else 0.0


def evaluate_equity_portfolio(
    data_by_symbol,
    strategy_config: V2Config,
    portfolio_config: EquityPortfolioConfig,
    instruments: dict[str, EquityInstrument] | None = None,
    *,
    point_in_time_membership: bool = False,
) -> EquityPortfolioResult:
    """Evaluate unchanged signals with shared capital and a pristine tail reserve.

    All instruments use the intersection of their trading calendars. The final
    ``reserved_holdout_sessions`` common sessions are removed before any signal,
    gate, or metric calculation.
    """
    if not data_by_symbol:
        raise ValueError("at least one symbol is required")
    dates, aligned = _aligned_rows(data_by_symbol)
    reserve = portfolio_config.reserved_holdout_sessions
    minimum = strategy_config.train_size + strategy_config.test_size + reserve
    if len(dates) < minimum:
        raise ValueError(f"need at least {minimum} common sessions; found {len(dates)}")
    holdout_start = dates[-reserve]
    dates = dates[:-reserve]
    aligned = {symbol: rows[:-reserve] for symbol, rows in aligned.items()}
    symbols = tuple(sorted(aligned))
    specs = instruments or {symbol: EquityInstrument(symbol=symbol) for symbol in symbols}

    eligible = []
    for symbol in symbols:
        volumes = [row.volume for row in aligned[symbol]]
        if median(volumes) >= specs[symbol].minimum_median_volume:
            eligible.append(symbol)
    symbols = tuple(eligible)
    if not symbols:
        raise ValueError("no symbol passed the median-volume liquidity gate")

    equity_execution = ExecutionConfig(
        initial_capital=portfolio_config.initial_capital,
        position_size=1,
        transaction_cost=portfolio_config.transaction_cost,
        slippage=portfolio_config.slippage,
        force_liquidation=False,
    )
    trading_by_symbol = {
        symbol: create_v2_trading_config(strategy_config.model_copy(update={
            "symbol": symbol, "execution": equity_execution,
        }))
        for symbol in symbols
    }
    decisions = defaultdict(dict)
    accepted_windows = 0
    total_windows = 0
    for symbol in symbols:
        rows = aligned[symbol]
        start = strategy_config.train_size
        while start + strategy_config.test_size <= len(rows):
            result = run_backtest(
                rows[start - strategy_config.train_size:start],
                trading_by_symbol[symbol], verbose=False,
            )
            accepted = (
                result.total_pnl > strategy_config.minimum_train_pnl
                and len(result.trades) >= strategy_config.minimum_train_trades
            )
            decisions[symbol][start] = accepted
            accepted_windows += int(accepted)
            total_windows += 1
            start += strategy_config.test_size

    cash = portfolio_config.initial_capital
    positions = {}
    pending = {}
    allowed = {symbol: False for symbol in symbols}
    equity_curve = []
    equity_dates = []
    completed = wins = rejected = 0
    turnover = costs = occupied_slots = 0.0
    target_value = portfolio_config.initial_capital * portfolio_config.allocation_fraction

    def sell(symbol, row):
        nonlocal cash, completed, wins, turnover, costs
        state = positions.pop(symbol)
        price = row.open - portfolio_config.slippage
        quantity = state["quantity"]
        cash += price * quantity - portfolio_config.transaction_cost / 2
        profit = ((price - state["entry_price"]) * quantity
                  - portfolio_config.transaction_cost)
        completed += 1
        wins += int(profit > 0)
        turnover += price * quantity
        costs += portfolio_config.transaction_cost / 2

    final_index = max(max(items) for items in decisions.values()) + strategy_config.test_size
    for index in range(strategy_config.train_size, final_index):
        # The gate uses only candles ending before this session's open.
        for symbol in symbols:
            if index in decisions[symbol]:
                allowed[symbol] = decisions[symbol][index]
                if not allowed[symbol]:
                    pending.pop(symbol, None)
                    if symbol in positions:
                        sell(symbol, aligned[symbol][index])

        # Risk-reducing orders are deterministic and execute before new entries.
        for symbol in symbols:
            if pending.get(symbol, {}).get("action") == Action.SELL and symbol in positions:
                sell(symbol, aligned[symbol][index])
                pending.pop(symbol, None)
        for symbol in symbols:
            order = pending.pop(symbol, None)
            if not order or order["action"] != Action.BUY or symbol in positions:
                continue
            row = aligned[symbol][index]
            price = row.open + portfolio_config.slippage
            quantity = int(min(target_value, cash - portfolio_config.transaction_cost / 2) / price)
            quantity -= quantity % specs[symbol].quantity_step
            if len(positions) >= portfolio_config.max_positions or quantity <= 0:
                rejected += 1
                continue
            cash -= price * quantity + portfolio_config.transaction_cost / 2
            positions[symbol] = {
                "quantity": quantity, "entry_price": price, "entry_atr": order["atr"],
            }
            turnover += price * quantity
            costs += portfolio_config.transaction_cost / 2

        for symbol in symbols:
            if not allowed[symbol]:
                continue
            rows = aligned[symbol]
            config = trading_by_symbol[symbol]
            features = build_market_features(
                rows[:index + 1], fast_sma_period=config.fast_sma_period,
                slow_sma_period=config.slow_sma_period, rsi_period=config.rsi_period,
                macd_fast_period=config.macd_fast_period,
                macd_slow_period=config.macd_slow_period,
                macd_signal_period=config.macd_signal_period,
                atr_period=config.atr_period,
            )
            signal = generate_trend_momentum_signal(features)
            state = positions.get(symbol)
            if state and state["entry_atr"] is not None and (
                rows[index].close <= state["entry_price"]
                - config.atr_stop_multiple * state["entry_atr"]
            ):
                signal = signal.model_copy(update={"action": Action.SELL})
            pending[symbol] = {"action": signal.action, "atr": features.atr}

        occupied_slots += len(positions)
        equity_curve.append(cash + sum(
            state["quantity"] * aligned[symbol][index].close
            for symbol, state in positions.items()
        ))
        equity_dates.append(dates[index])

    final_equity = equity_curve[-1]
    pnl = final_equity - portfolio_config.initial_capital
    yearly = {}
    previous = portfolio_config.initial_capital
    for year in sorted({day.year for day in equity_dates}):
        year_values = [value for day, value in zip(equity_dates, equity_curve)
                       if day.year == year]
        yearly[year] = year_values[-1] - previous
        previous = year_values[-1]

    # Equal-capital passive comparison on the identical common-date span.
    allocation = portfolio_config.initial_capital / len(symbols)
    benchmark_cash = portfolio_config.initial_capital
    benchmark_quantities = {}
    first_index = strategy_config.train_size
    for symbol in symbols:
        price = aligned[symbol][first_index].open + portfolio_config.slippage
        quantity = int((allocation - portfolio_config.transaction_cost / 2) / price)
        benchmark_quantities[symbol] = quantity
        benchmark_cash -= quantity * price + portfolio_config.transaction_cost / 2
    benchmark_equity = benchmark_cash + sum(
        benchmark_quantities[symbol] * aligned[symbol][final_index - 1].close
        for symbol in symbols
    )
    benchmark_pnl = benchmark_equity - portfolio_config.initial_capital

    return EquityPortfolioResult(
        symbols=symbols, first_development_date=equity_dates[0],
        last_development_date=equity_dates[-1], reserved_holdout_start=holdout_start,
        sessions=len(equity_dates), total_pnl=pnl,
        total_return=pnl / portfolio_config.initial_capital * 100,
        max_drawdown=calculate_max_drawdown(equity_curve),
        annualized_sharpe=_sharpe(equity_curve), completed_trades=completed,
        win_rate=wins / completed * 100 if completed else 0,
        exposure_percent=(occupied_slots / (len(equity_curve) * portfolio_config.max_positions)
                          * 100), turnover=turnover, transaction_costs=costs,
        rejected_orders=rejected, accepted_symbol_windows=accepted_windows,
        total_symbol_windows=total_windows, benchmark_pnl=benchmark_pnl,
        excess_pnl=pnl - benchmark_pnl, yearly_pnl=yearly,
        survivorship_bias_warning=not point_in_time_membership,
    )


def run_robustness_scenarios(data_by_symbol, strategy_config, portfolio_config, **kwargs):
    """Run fixed, declared friction scenarios; this is not parameter optimization."""
    scenarios = {
        "base": portfolio_config,
        "double_slippage": portfolio_config.model_copy(
            update={"slippage": portfolio_config.slippage * 2}),
        "double_cost": portfolio_config.model_copy(
            update={"transaction_cost": portfolio_config.transaction_cost * 2}),
        "combined_stress": portfolio_config.model_copy(update={
            "slippage": portfolio_config.slippage * 2,
            "transaction_cost": portfolio_config.transaction_cost * 2,
        }),
    }
    return {
        name: evaluate_equity_portfolio(
            data_by_symbol, strategy_config, scenario, **kwargs,
        ) for name, scenario in scenarios.items()
    }
