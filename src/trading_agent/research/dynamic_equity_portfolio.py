"""Union-calendar shared-capital equity research for V3 Step 6."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import sqrt
from statistics import mean, median, pstdev

from pydantic import BaseModel, ConfigDict

from trading_agent.core.config import ExecutionConfig, V2Config
from trading_agent.core.dividends import DividendEvent, dividends_by_symbol_date
from trading_agent.core.equity import EquityInstrument, EquityPortfolioConfig
from trading_agent.core.fees import OrderSide, calculate_cash_equity_fees
from trading_agent.core.universe import UniverseMember, active_symbols, membership_status
from trading_agent.research.backtest import run_backtest
from trading_agent.research.experiment import create_v2_trading_config
from trading_agent.research.performance import calculate_max_drawdown
from trading_agent.signals.features import build_market_features
from trading_agent.signals.strategy import Action, generate_trend_momentum_signal


class DynamicPortfolioResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbols: tuple[str, ...]
    calendar_start: date
    calendar_end: date
    calendar_dates: tuple[date, ...]
    reserved_holdout_start: date
    sessions: int
    total_pnl: float
    total_return: float
    max_drawdown: float
    annualized_sharpe: float
    completed_trades: int
    exposure_percent: float
    turnover: float
    transaction_costs: float
    dividend_cash: float
    benchmark_pnl: float
    benchmark_dividend_cash: float
    excess_pnl: float
    yearly_pnl: dict[int, float]
    contributions: dict[str, float]
    membership_status: str
    price_return_benchmark_only: bool


def _sharpe(values):
    returns = [b / a - 1 for a, b in zip(values, values[1:]) if a]
    volatility = pstdev(returns) if len(returns) > 1 else 0
    return mean(returns) / volatility * sqrt(252) if volatility else 0.0


def evaluate_dynamic_equity_portfolio(
    data_by_symbol,
    strategy_config: V2Config,
    portfolio_config: EquityPortfolioConfig,
    *,
    development_start: date,
    development_end: date,
    reserved_holdout_start: date = date(2025, 9, 1),
    instruments: dict[str, EquityInstrument] | None = None,
    universe_members: list[UniverseMember] | None = None,
    indexes: set[str] | None = None,
    retrospective_static_membership: bool = False,
    dividends: list[DividendEvent] | None = None,
) -> DynamicPortfolioResult:
    """Evaluate on the union calendar; never load a candle in the reserved tail."""
    if development_end >= reserved_holdout_start:
        raise ValueError("development_end must precede the reserved holdout")
    if development_start > development_end:
        raise ValueError("invalid development cohort")
    histories = {
        symbol: sorted(
            (row for row in rows if row.date.date() < reserved_holdout_start),
            key=lambda row: row.date,
        )
        for symbol, rows in data_by_symbol.items()
    }
    histories = {symbol: rows for symbol, rows in histories.items() if rows}
    if not histories:
        raise ValueError("no pre-holdout histories")
    row_maps = {
        symbol: {row.date.date(): (index, row) for index, row in enumerate(rows)}
        for symbol, rows in histories.items()
    }
    calendar = sorted({
        day for mapping in row_maps.values() for day in mapping
        if development_start <= day <= development_end
    })
    if not calendar:
        raise ValueError("cohort has no exchange sessions")
    specs = instruments or {
        symbol: EquityInstrument(symbol=symbol) for symbol in histories
    }
    if universe_members is None:
        status = "long_history_static_cohort" if retrospective_static_membership else "membership_unavailable"
    else:
        status = membership_status(universe_members, development_start, development_end)
        if status == "retrospective_current_snapshot" and not retrospective_static_membership:
            raise ValueError("historical membership unavailable; explicit retrospective mode required")

    execution = ExecutionConfig(
        initial_capital=portfolio_config.initial_capital, position_size=1,
        transaction_cost=portfolio_config.transaction_cost,
        slippage=portfolio_config.slippage, force_liquidation=False,
        fee_schedule=portfolio_config.fee_schedule,
    )
    trading = {
        symbol: create_v2_trading_config(strategy_config.model_copy(update={
            "symbol": symbol, "execution": execution,
        })) for symbol in histories
    }
    decisions = defaultdict(dict)
    for symbol, rows in histories.items():
        start = strategy_config.train_size
        while start < len(rows):
            result = run_backtest(
                rows[start - strategy_config.train_size:start], trading[symbol], verbose=False,
            )
            decisions[symbol][start] = (
                result.total_pnl > strategy_config.minimum_train_pnl
                and len(result.trades) >= strategy_config.minimum_train_trades
            )
            start += strategy_config.test_size

    def fee(price, quantity, side):
        if quantity <= 0:
            return 0.0
        if portfolio_config.fee_schedule is None:
            return portfolio_config.transaction_cost / 2
        return float(calculate_cash_equity_fees(
            price, quantity, side, portfolio_config.fee_schedule,
        ).total)

    dividend_map = dividends_by_symbol_date(dividends)
    cash = portfolio_config.initial_capital
    positions, pending = {}, {}
    allowed = {symbol: False for symbol in histories}
    equity_curve, equity_dates = [], []
    turnover = costs = exposure = dividend_cash = 0.0
    trades = 0
    contributions = defaultdict(float)
    target = portfolio_config.initial_capital * portfolio_config.allocation_fraction

    def eligible_members(day):
        if universe_members is None or retrospective_static_membership:
            return set(histories)
        return active_symbols(universe_members, day, indexes, require_snapshot=True)

    def sell(symbol, row):
        nonlocal cash, turnover, costs, trades
        state = positions.pop(symbol)
        price = row.open - portfolio_config.slippage
        charge = fee(price, state["quantity"], OrderSide.SELL)
        proceeds = price * state["quantity"] - charge
        cash += proceeds
        pnl = proceeds - state["basis"]
        contributions[symbol] += pnl
        turnover += price * state["quantity"]
        costs += charge
        trades += 1

    for day in calendar:
        members = eligible_members(day)
        available = {
            symbol: row_maps[symbol][day] for symbol in histories
            if day in row_maps[symbol] and symbol in members
        }
        # Ex-date cash belongs to positions carried into the session; a sale at
        # the ex-date open retains entitlement and a new ex-date buy does not.
        for symbol, state in positions.items():
            amount = dividend_map.get((symbol, day), 0) * state["quantity"]
            cash += amount
            dividend_cash += amount
            contributions[symbol] += amount
        # Membership removal is risk-reducing, but can execute only on a valid row.
        for symbol in list(positions):
            if symbol not in members and day in row_maps[symbol]:
                sell(symbol, row_maps[symbol][day][1])
                pending.pop(symbol, None)

        for symbol, (index, row) in available.items():
            if index in decisions[symbol]:
                allowed[symbol] = decisions[symbol][index]
                if not allowed[symbol]:
                    pending.pop(symbol, None)
                    if symbol in positions:
                        sell(symbol, row)

        # Execute exits before entries on each union-calendar session.
        for symbol in sorted(available):
            if pending.get(symbol, {}).get("action") == Action.SELL and symbol in positions:
                sell(symbol, available[symbol][1])
                pending.pop(symbol, None)
        for symbol in sorted(available):
            order = pending.pop(symbol, None)
            if not order or order["action"] != Action.BUY or symbol in positions:
                continue
            if len(positions) >= portfolio_config.max_positions:
                continue
            row = available[symbol][1]
            price = row.open + portfolio_config.slippage
            quantity = int(min(target, cash) / price)
            quantity -= quantity % specs[symbol].quantity_step
            while quantity > 0 and price * quantity + fee(price, quantity, OrderSide.BUY) > cash:
                quantity -= specs[symbol].quantity_step
            if quantity <= 0:
                continue
            charge = fee(price, quantity, OrderSide.BUY)
            basis = price * quantity + charge
            cash -= basis
            positions[symbol] = {
                "quantity": quantity, "entry_price": price,
                "entry_atr": order["atr"], "basis": basis,
            }
            turnover += price * quantity
            costs += charge

        for symbol, (index, row) in available.items():
            if not allowed[symbol] or index < strategy_config.train_size:
                continue
            prior_volumes = [item.volume for item in histories[symbol][:index + 1]]
            if median(prior_volumes) < specs[symbol].minimum_median_volume:
                continue
            features = build_market_features(
                histories[symbol][:index + 1],
                fast_sma_period=trading[symbol].fast_sma_period,
                slow_sma_period=trading[symbol].slow_sma_period,
                rsi_period=trading[symbol].rsi_period,
                macd_fast_period=trading[symbol].macd_fast_period,
                macd_slow_period=trading[symbol].macd_slow_period,
                macd_signal_period=trading[symbol].macd_signal_period,
                atr_period=trading[symbol].atr_period,
            )
            signal = generate_trend_momentum_signal(features)
            state = positions.get(symbol)
            if state and state["entry_atr"] is not None and (
                row.close <= state["entry_price"]
                - trading[symbol].atr_stop_multiple * state["entry_atr"]
            ):
                signal = signal.model_copy(update={"action": Action.SELL})
            pending[symbol] = {"action": signal.action, "atr": features.atr}

        value = cash
        for symbol, state in positions.items():
            prior = [row for row in histories[symbol] if row.date.date() <= day]
            value += state["quantity"] * prior[-1].close
        equity_curve.append(value)
        equity_dates.append(day)
        exposure += len(positions)

    # Equal-capital price benchmark, same cohort endpoints and union calendar.
    first_day = calendar[0]
    benchmark_symbols = sorted(
        symbol for symbol, mapping in row_maps.items() if first_day in mapping
        and symbol in eligible_members(first_day)
    )
    benchmark_cash = portfolio_config.initial_capital
    benchmark_positions = {}
    if benchmark_symbols:
        allocation = benchmark_cash / len(benchmark_symbols)
        for symbol in benchmark_symbols:
            row = row_maps[symbol][first_day][1]
            price = row.open + portfolio_config.slippage
            quantity = int(allocation / price)
            charge = fee(price, quantity, OrderSide.BUY)
            benchmark_cash -= price * quantity + charge
            benchmark_positions[symbol] = quantity
    benchmark_dividends = 0.0
    for (symbol, day), amount in dividend_map.items():
        if symbol in benchmark_positions and first_day <= day <= calendar[-1]:
            cash_amount = benchmark_positions[symbol] * amount
            benchmark_cash += cash_amount
            benchmark_dividends += cash_amount
    benchmark_equity = benchmark_cash
    for symbol, quantity in benchmark_positions.items():
        rows = [row for row in histories[symbol] if row.date.date() <= calendar[-1]]
        benchmark_equity += quantity * rows[-1].close

    pnl = equity_curve[-1] - portfolio_config.initial_capital
    yearly = {}
    previous = portfolio_config.initial_capital
    for year in sorted({day.year for day in equity_dates}):
        values = [value for day, value in zip(equity_dates, equity_curve) if day.year == year]
        yearly[year] = values[-1] - previous
        previous = values[-1]
    return DynamicPortfolioResult(
        symbols=tuple(sorted(histories)), calendar_start=calendar[0],
        calendar_end=calendar[-1], calendar_dates=tuple(calendar),
        reserved_holdout_start=reserved_holdout_start,
        sessions=len(calendar), total_pnl=pnl,
        total_return=pnl / portfolio_config.initial_capital * 100,
        max_drawdown=calculate_max_drawdown(equity_curve),
        annualized_sharpe=_sharpe(equity_curve), completed_trades=trades,
        exposure_percent=exposure / (len(calendar) * portfolio_config.max_positions) * 100,
        turnover=turnover, transaction_costs=costs, dividend_cash=dividend_cash,
        benchmark_pnl=benchmark_equity - portfolio_config.initial_capital,
        benchmark_dividend_cash=benchmark_dividends,
        excess_pnl=pnl - (benchmark_equity - portfolio_config.initial_capital),
        yearly_pnl=yearly, contributions=dict(contributions), membership_status=status,
        price_return_benchmark_only=not bool(dividends),
    )
