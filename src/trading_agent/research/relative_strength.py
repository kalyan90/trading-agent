"""V4 Step 1 predeclared monthly cross-sectional relative-strength baseline."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import sqrt
from statistics import mean, median, pstdev

from pydantic import BaseModel, ConfigDict

from trading_agent.core.dividends import DividendEvent, dividends_by_symbol_date
from trading_agent.core.equity import EquityInstrument, EquityPortfolioConfig
from trading_agent.core.fees import OrderSide, calculate_cash_equity_fees
from trading_agent.core.universe import UniverseMember, active_symbols, membership_status
from trading_agent.research.performance import calculate_max_drawdown


MOMENTUM_LOOKBACK = 252
MOMENTUM_SKIP = 21
TOP_N = 10
REGIME_SMA_PERIOD = 200


class RelativeStrengthResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbols: tuple[str, ...]
    calendar_dates: tuple[date, ...]
    reserved_holdout_start: date
    total_pnl: float
    total_return: float
    max_drawdown: float
    annualized_sharpe: float
    turnover: float
    transaction_costs: float
    completed_sales: int
    rejected_orders: int
    deferred_orders: int
    exposure_percent: float
    ending_cash: float
    dividend_cash: float
    benchmark_pnl: float
    benchmark_start_date: date | None
    benchmark_dividend_cash: float
    excess_pnl: float
    yearly_pnl: dict[int, float]
    contributions: dict[str, float]
    monthly_selections: dict[date, tuple[str, ...]]
    membership_status: str
    price_return_benchmark_only: bool
    execution_log: tuple[str, ...]
    monthly_rankings: dict[date, tuple[str, ...]]
    regime_risk_on_months: int = 0
    regime_risk_off_months: int = 0
    regime_missing_months: int = 0


def momentum_score(rows, index: int) -> float | None:
    """12-minus-1 momentum, excluding the most recent 21 observations."""
    if index < MOMENTUM_LOOKBACK:
        return None
    old = rows[index - MOMENTUM_LOOKBACK].close
    recent = rows[index - MOMENTUM_SKIP].close
    return recent / old - 1 if old > 0 else None


def rank_relative_strength(scores: dict[str, float]) -> tuple[str, ...]:
    """Select positive scores by descending momentum, symbol-breaking ties."""
    ranked = sorted(
        ((score, symbol) for symbol, score in scores.items() if score > 0),
        key=lambda item: (-item[0], item[1]),
    )
    return tuple(symbol for _, symbol in ranked[:TOP_N])


def regime_risk_on(regime_rows, signal_date: date) -> tuple[bool, str]:
    """Use exactly the 200 closes ending on signal_date; missing means risk-off."""
    by_date = {row.date.date(): index for index, row in enumerate(regime_rows)}
    index = by_date.get(signal_date)
    if index is None or index + 1 < REGIME_SMA_PERIOD:
        return False, "missing_date_or_history"
    closes = [row.close for row in regime_rows[index - REGIME_SMA_PERIOD + 1:index + 1]]
    average = sum(closes) / REGIME_SMA_PERIOD
    return regime_rows[index].close > average, "available"


def _sharpe(values):
    returns = [right / left - 1 for left, right in zip(values, values[1:]) if left]
    volatility = pstdev(returns) if len(returns) > 1 else 0
    return mean(returns) / volatility * sqrt(252) if volatility else 0.0


def evaluate_relative_strength(
    data_by_symbol,
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
    regime_history=None,
) -> RelativeStrengthResult:
    if development_end >= reserved_holdout_start:
        raise ValueError("development_end must precede the reserved holdout")
    histories = {
        symbol: sorted(
            (row for row in rows if row.date.date() < reserved_holdout_start),
            key=lambda row: row.date,
        ) for symbol, rows in data_by_symbol.items()
    }
    histories = {symbol: rows for symbol, rows in histories.items() if rows}
    row_maps = {
        symbol: {row.date.date(): (index, row) for index, row in enumerate(rows)}
        for symbol, rows in histories.items()
    }
    calendar = sorted({
        day for mapping in row_maps.values() for day in mapping
        if development_start <= day <= development_end
    })
    if not calendar:
        raise ValueError("cohort has no sessions")
    month_ends = {
        max(day for day in calendar if (day.year, day.month) == month)
        for month in {(day.year, day.month) for day in calendar}
    }
    specs = instruments or {
        symbol: EquityInstrument(symbol=symbol) for symbol in histories
    }
    if universe_members is None:
        status = "long_history_static_cohort" if retrospective_static_membership else "membership_unavailable"
    else:
        status = membership_status(universe_members, development_start, development_end)
        if status == "retrospective_current_snapshot" and not retrospective_static_membership:
            raise ValueError("historical membership unavailable; explicit retrospective mode required")

    def members(day):
        if universe_members is None or retrospective_static_membership:
            return set(histories)
        return active_symbols(universe_members, day, indexes, require_snapshot=True)

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
    target_value = portfolio_config.initial_capital / TOP_N
    positions = {}
    pending_targets = {}
    equity_curve = []
    turnover = costs = exposure = dividend_cash = 0.0
    rejected = deferred = completed_sales = 0
    contributions = defaultdict(float)
    selections = {}
    rankings = {}
    execution_log = []
    risk_on_months = risk_off_months = missing_regime_months = 0

    def reduce(symbol, quantity, row):
        nonlocal cash, turnover, costs, completed_sales
        state = positions[symbol]
        price = row.open - portfolio_config.slippage
        charge = fee(price, quantity, OrderSide.SELL)
        basis_part = state["basis"] * quantity / state["quantity"]
        proceeds = price * quantity - charge
        cash += proceeds
        state["quantity"] -= quantity
        state["basis"] -= basis_part
        contributions[symbol] += proceeds - basis_part
        turnover += price * quantity
        costs += charge
        completed_sales += 1
        execution_log.append(f"SELL:{symbol}:{row.date.date().isoformat()}")
        if state["quantity"] == 0:
            positions.pop(symbol)

    for calendar_index, day in enumerate(calendar):
        available_members = members(day)
        available = {
            symbol: row_maps[symbol][day] for symbol in histories
            if day in row_maps[symbol] and symbol in available_members
        }
        for symbol, state in positions.items():
            amount = dividend_map.get((symbol, day), 0) * state["quantity"]
            cash += amount
            dividend_cash += amount
            contributions[symbol] += amount

        # Pending month-end targets execute only at a later available open.
        executable = {
            symbol: target for symbol, target in pending_targets.items()
            if symbol in available and day > target["signal_date"]
        }
        # Determine desired whole shares at each symbol's own next open.
        desired = {}
        for symbol, order in executable.items():
            if order["selected"]:
                price = available[symbol][1].open + portfolio_config.slippage
                desired[symbol] = int(target_value / price)
            else:
                desired[symbol] = 0
        # Sells/reductions always precede buys/increases.
        for symbol in sorted(desired):
            current = positions.get(symbol, {}).get("quantity", 0)
            if current > desired[symbol]:
                reduce(symbol, current - desired[symbol], available[symbol][1])
        for symbol in sorted(desired):
            current = positions.get(symbol, {}).get("quantity", 0)
            quantity = desired[symbol] - current
            if quantity <= 0:
                pending_targets.pop(symbol, None)
                continue
            row = available[symbol][1]
            price = row.open + portfolio_config.slippage
            charge = fee(price, quantity, OrderSide.BUY)
            if price * quantity + charge > cash:
                affordable = int(cash / price)
                while affordable > 0 and price * affordable + fee(
                    price, affordable, OrderSide.BUY,
                ) > cash:
                    affordable -= 1
                quantity = min(quantity, affordable)
            if quantity <= 0:
                rejected += 1
                pending_targets.pop(symbol, None)
                continue
            charge = fee(price, quantity, OrderSide.BUY)
            basis = price * quantity + charge
            cash -= basis
            if symbol in positions:
                positions[symbol]["quantity"] += quantity
                positions[symbol]["basis"] += basis
            else:
                positions[symbol] = {"quantity": quantity, "basis": basis}
            turnover += price * quantity
            costs += charge
            execution_log.append(f"BUY:{symbol}:{day.isoformat()}")
            pending_targets.pop(symbol, None)
        for symbol, order in pending_targets.items():
            if (day > order["signal_date"] and not order["deferred_counted"]
                    and symbol not in available):
                order["deferred_counted"] = True
                deferred += 1

        if day in month_ends:
            scores = {}
            for symbol, (index, row) in available.items():
                if index < MOMENTUM_LOOKBACK:
                    continue
                if median(item.volume for item in histories[symbol][:index + 1]) < specs[symbol].minimum_median_volume:
                    continue
                score = momentum_score(histories[symbol], index)
                if score is not None:
                    scores[symbol] = score
            ranked = rank_relative_strength(scores)
            rankings[day] = ranked
            if regime_history is None:
                risk_on, regime_status = True, "disabled"
            else:
                risk_on, regime_status = regime_risk_on(regime_history, day)
                if regime_status != "available":
                    missing_regime_months += 1
                if risk_on:
                    risk_on_months += 1
                else:
                    risk_off_months += 1
            selected = ranked if risk_on else ()
            selections[day] = selected
            selected_set = set(selected)
            for symbol in set(histories) | set(positions):
                pending_targets[symbol] = {
                    "signal_date": day, "selected": symbol in selected_set,
                    "deferred_counted": False,
                }

        value = cash
        for symbol, state in positions.items():
            prior = [row for row in histories[symbol] if row.date.date() <= day]
            value += state["quantity"] * prior[-1].close
        equity_curve.append(value)
        exposure += sum(state["basis"] for state in positions.values()) / portfolio_config.initial_capital

    # Add unrealized attribution without forcing liquidation.
    final_contributions = dict(contributions)
    for symbol, state in positions.items():
        prior = [row for row in histories[symbol] if row.date.date() <= calendar[-1]]
        final_contributions[symbol] = final_contributions.get(symbol, 0) + (
            state["quantity"] * prior[-1].close - state["basis"]
        )

    # Matching equal-weight price benchmark using symbols eligible on cohort start.
    # Benchmark eligibility follows the underlying Step 1 ranking, not an overlay
    # that may temporarily keep the strategy in cash.
    first_signal = next((day for day in sorted(rankings) if rankings[day]), None)
    benchmark_start = None
    if first_signal is not None:
        benchmark_start = next((day for day in calendar if day > first_signal), None)
    benchmark_symbols = []
    if benchmark_start is not None:
        for symbol in sorted(members(benchmark_start)):
            if symbol not in row_maps or benchmark_start not in row_maps[symbol]:
                continue
            index, _ = row_maps[symbol][benchmark_start]
            if (index >= MOMENTUM_LOOKBACK and median(
                    item.volume for item in histories[symbol][:index + 1]
            ) >= specs[symbol].minimum_median_volume):
                benchmark_symbols.append(symbol)
    benchmark_cash = portfolio_config.initial_capital
    benchmark_positions = {}
    if benchmark_symbols:
        allocation = benchmark_cash / len(benchmark_symbols)
        for symbol in benchmark_symbols:
            row = row_maps[symbol][benchmark_start][1]
            price = row.open + portfolio_config.slippage
            quantity = int(allocation / price)
            charge = fee(price, quantity, OrderSide.BUY)
            benchmark_cash -= price * quantity + charge
            benchmark_positions[symbol] = quantity
    benchmark_dividends = 0.0
    for (symbol, event_day), amount in dividend_map.items():
        if (symbol in benchmark_positions and benchmark_start is not None
                and benchmark_start <= event_day <= calendar[-1]):
            payment = amount * benchmark_positions[symbol]
            benchmark_cash += payment
            benchmark_dividends += payment
    benchmark_equity = benchmark_cash
    for symbol, quantity in benchmark_positions.items():
        prior = [row for row in histories[symbol] if row.date.date() <= calendar[-1]]
        benchmark_equity += quantity * prior[-1].close

    final_equity = equity_curve[-1]
    pnl = final_equity - portfolio_config.initial_capital
    yearly = {}
    previous = portfolio_config.initial_capital
    for year in sorted({day.year for day in calendar}):
        values = [value for day, value in zip(calendar, equity_curve) if day.year == year]
        yearly[year] = values[-1] - previous
        previous = values[-1]
    return RelativeStrengthResult(
        symbols=tuple(sorted(histories)), calendar_dates=tuple(calendar),
        reserved_holdout_start=reserved_holdout_start, total_pnl=pnl,
        total_return=pnl / portfolio_config.initial_capital * 100,
        max_drawdown=calculate_max_drawdown(equity_curve),
        annualized_sharpe=_sharpe(equity_curve), turnover=turnover,
        transaction_costs=costs, completed_sales=completed_sales,
        rejected_orders=rejected, deferred_orders=deferred,
        exposure_percent=exposure / len(calendar) * 100,
        ending_cash=cash, dividend_cash=dividend_cash,
        benchmark_pnl=benchmark_equity - portfolio_config.initial_capital,
        benchmark_start_date=benchmark_start,
        benchmark_dividend_cash=benchmark_dividends,
        excess_pnl=pnl - (benchmark_equity - portfolio_config.initial_capital),
        yearly_pnl=yearly, contributions=final_contributions,
        monthly_selections=selections, membership_status=status,
        price_return_benchmark_only=not bool(dividends),
        execution_log=tuple(execution_log),
        monthly_rankings=rankings,
        regime_risk_on_months=risk_on_months,
        regime_risk_off_months=risk_off_months,
        regime_missing_months=missing_regime_months,
    )
