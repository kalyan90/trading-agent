"""V3 real-futures loading, rollover, and execution."""

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from trading_agent.research.backtest import run_backtest
from trading_agent.core.config import V2Config
from trading_agent.research.experiment import create_v2_trading_config
from trading_agent.signals.features import build_market_features
from trading_agent.research.performance import calculate_max_drawdown
from trading_agent.signals.strategy import Action, generate_trend_momentum_signal
from trading_agent.execution.futures_account import (
    FuturesAccount, FuturesChargeConfig, FuturesMarginConfig,
)


class FuturesMarketData(BaseModel):
    date: datetime
    expiry: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    settlement_price: float
    volume: int
    open_interest: int
    market_lot: int
    underlying_value: float | None = None


def load_futures_contracts(data_dir: Path) -> list[FuturesMarketData]:
    raw_rows = []
    for path in sorted(data_dir.glob("nifty_futures_contracts_*.csv")):
        with path.open(encoding="utf-8") as source:
            raw_rows.extend(csv.DictReader(source))

    lots_by_expiry = {}
    for expiry in {row["expiry"] for row in raw_rows}:
        values = [int(float(row["market_lot"])) for row in raw_rows
                  if row["expiry"] == expiry and row["market_lot"]]
        if values:
            lots_by_expiry[expiry] = Counter(values).most_common(1)[0][0]

    records = []
    for row in raw_rows:
        required_prices = ("open", "high", "low", "close", "settlement_price")
        if any(not row[field] for field in required_prices):
            continue
        lot = int(float(row["market_lot"])) if row["market_lot"] else lots_by_expiry.get(row["expiry"])
        if lot is None:
            raise ValueError(f"No market lot available for expiry {row['expiry']}")
        records.append(FuturesMarketData(
            date=datetime.strptime(row["date"], "%d-%b-%Y"),
            expiry=datetime.strptime(row["expiry"], "%d-%b-%Y"),
            symbol=row["symbol"], open=float(row["open"]), high=float(row["high"]),
            low=float(row["low"]), close=float(row["close"]),
            settlement_price=float(row["settlement_price"]),
            volume=int(float(row["traded_quantity"])),
            open_interest=int(float(row["open_interest"])), market_lot=lot,
            underlying_value=float(row["underlying_value"]) if row["underlying_value"] else None,
        ))
    return sorted(records, key=lambda item: (item.date, item.expiry))


def build_front_month_series(contracts: list[FuturesMarketData]):
    """Choose the nearest unexpired contract; roll after its expiry session."""
    by_date = {}
    for contract in contracts:
        if contract.expiry.date() >= contract.date.date():
            by_date.setdefault(contract.date.date(), []).append(contract)
    return [min(by_date[day], key=lambda item: item.expiry)
            for day in sorted(by_date)]


class FuturesExecutionResult(BaseModel):
    starting_capital: float
    accepted_windows: int
    rejected_windows: int
    strategy_trades: int
    gate_liquidations: int
    rolls: int
    final_equity: float
    total_pnl: float
    total_return: float
    max_drawdown: float
    exposure_percent: float
    missing_futures_dates: int
    rejected_entries: int = 0
    margin_calls: int = 0
    peak_margin: float = 0
    minimum_free_cash: float = 0
    benchmark_pnl: float = 0
    benchmark_entry_rejected: bool = False
    benchmark_margin_calls: int = 0
    total_charges: float = 0


def evaluate_futures_benchmark(
    spot_data, future_by_date, start_index, end_index, trading, margin_config,
    initial_capital, charge_config,
):
    """Continuously hold the same front-month contract with identical funding."""
    account = FuturesAccount(
        initial_capital, trading.transaction_cost, margin_config, charge_config
    )
    held_expiry = None
    last_future = None
    rejected = False
    margin_calls = 0
    liquidate = False

    for spot in spot_data[start_index:end_index]:
        future = future_by_date.get(spot.date.date())
        if future is None:
            continue
        if liquidate:
            account.close(future.open - trading.slippage, future.date.date())
            margin_calls += 1
            break
        if account.is_open and held_expiry != future.expiry:
            account.close(last_future.settlement_price - trading.slippage,
                          last_future.date.date())
            if not account.open(future.open + trading.slippage, future.market_lot,
                                future.date.date()):
                rejected = True
                break
            held_expiry = future.expiry
        elif not account.is_open:
            if not account.open(future.open + trading.slippage, future.market_lot,
                                future.date.date()):
                rejected = True
                break
            held_expiry = future.expiry
        liquidate = account.settle(future.settlement_price)
        last_future = future

    return account.cash - initial_capital, rejected, margin_calls


def evaluate_futures_execution(
    spot_data, futures_series, config: V2Config,
    margin_config: FuturesMarginConfig | None = None,
    initial_capital: float | None = None,
    charge_config: FuturesChargeConfig | None = None,
):
    """Use spot features/gates and execute a continuous portfolio in futures."""
    trading = create_v2_trading_config(config)
    future_by_date = {item.date.date(): item for item in futures_series}
    decisions = {}
    start = config.train_size
    while start + config.test_size <= len(spot_data):
        train = spot_data[start - config.train_size:start]
        result = run_backtest(train, trading, verbose=False)
        decisions[start] = result.total_pnl > 0 and len(result.trades) >= config.minimum_train_trades
        start += config.test_size

    starting_capital = initial_capital or trading.initial_capital
    account = FuturesAccount(
        starting_capital, trading.transaction_cost, margin_config, charge_config
    )
    position = False
    entry_price = entry_atr = None
    lot = 0
    held_expiry = None
    pending = None
    pending_atr = None
    strategy_trades = gate_liquidations = rolls = 0
    rejected_entries = margin_calls = 0
    exposed = eligible = missing = 0
    equity = []
    allowed = False
    last_future = None
    liquidation_reason = None

    for index in range(config.train_size, max(decisions) + config.test_size):
        spot = spot_data[index]
        if index in decisions:
            allowed = decisions[index]
            if not allowed:
                pending = None
                pending_atr = None
                if position:
                    liquidation_reason = "gate"

        future = future_by_date.get(spot.date.date())
        if future is None:
            missing += 1
            continue
        eligible += 1

        if liquidation_reason:
            account.close(future.open - trading.slippage, future.date.date())
            position = False
            entry_price = entry_atr = None
            held_expiry = None
            lot = 0
            strategy_trades += 1
            if liquidation_reason == "gate":
                gate_liquidations += 1
            else:
                margin_calls += 1
            liquidation_reason = None

        if position and held_expiry != future.expiry:
            exit_price = last_future.settlement_price - trading.slippage
            account.close(exit_price, last_future.date.date())
            position = False
            rolls += 1
            if allowed:
                entry_price = future.open + trading.slippage
                lot = future.market_lot
                position = account.open(entry_price, lot, future.date.date())
                if position:
                    held_expiry = future.expiry
                else:
                    rejected_entries += 1
                    entry_price = entry_atr = None
                    held_expiry = None
                    lot = 0
            pending = None

        if allowed and pending == Action.BUY and not position:
            entry_price = future.open + trading.slippage
            entry_atr = pending_atr
            lot = future.market_lot
            held_expiry = future.expiry
            position = account.open(entry_price, lot, future.date.date())
            if not position:
                rejected_entries += 1
                entry_price = entry_atr = None
                held_expiry = None
                lot = 0
        elif allowed and pending == Action.SELL and position:
            account.close(future.open - trading.slippage, future.date.date())
            position = False
            entry_price = entry_atr = None
            held_expiry = None
            lot = 0
            strategy_trades += 1

        if allowed:
            features = build_market_features(spot_data[:index + 1])
            signal = generate_trend_momentum_signal(features)
            if position and entry_atr is not None and future.settlement_price <= entry_price - 2 * entry_atr:
                signal = signal.model_copy(update={"action": Action.SELL})
            pending, pending_atr = signal.action, features.atr
        else:
            pending = None

        if position:
            exposed += 1
            if account.settle(future.settlement_price):
                liquidation_reason = "margin"
        equity.append(account.cash)
        last_future = future

    final_equity = equity[-1]
    pnl = final_equity - starting_capital
    benchmark_pnl, benchmark_rejected, benchmark_margin_calls = (
        evaluate_futures_benchmark(
            spot_data, future_by_date, config.train_size,
            max(decisions) + config.test_size, trading, margin_config,
            starting_capital, charge_config,
        )
    )
    return FuturesExecutionResult(
        starting_capital=starting_capital,
        accepted_windows=sum(decisions.values()),
        rejected_windows=len(decisions) - sum(decisions.values()),
        strategy_trades=strategy_trades, gate_liquidations=gate_liquidations,
        rolls=rolls, final_equity=final_equity,
        total_pnl=pnl, total_return=pnl / starting_capital * 100,
        max_drawdown=calculate_max_drawdown(equity),
        exposure_percent=exposed / eligible * 100 if eligible else 0,
        missing_futures_dates=missing, rejected_entries=rejected_entries,
        margin_calls=margin_calls, peak_margin=account.peak_margin,
        minimum_free_cash=account.minimum_free_cash,
        benchmark_pnl=benchmark_pnl,
        benchmark_entry_rejected=benchmark_rejected,
        benchmark_margin_calls=benchmark_margin_calls,
        total_charges=account.total_charges,
    )
