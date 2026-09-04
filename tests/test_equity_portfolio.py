import math
from datetime import datetime, timedelta

from trading_agent.core.config import ExecutionConfig, V2Config
from trading_agent.core.equity import EquityInstrument, EquityPortfolioConfig
from trading_agent.core.market import MarketData
from trading_agent.core.universe import UniverseMember
from trading_agent.research.equity_portfolio import (
    evaluate_equity_portfolio, run_robustness_scenarios,
)


def history(symbol, reserve_delta=0):
    rows = []
    for index in range(150):
        close = 100 + index * 0.08 + math.sin(index / 3) * 8
        if index >= 130:
            close += reserve_delta
        rows.append(MarketData(
            date=datetime(2024, 1, 1) + timedelta(days=index), symbol=symbol,
            open=close - 0.2, high=close + 1, low=close - 1,
            close=close, volume=500_000,
        ))
    return rows


STRATEGY = V2Config(
    train_size=60, test_size=20, slow_sma_period=10, fast_sma_period=5,
    rsi_period=5, macd_fast_period=4, macd_slow_period=8,
    macd_signal_period=3, atr_period=5, minimum_train_trades=1,
    execution=ExecutionConfig(
        initial_capital=100_000, position_size=1,
        transaction_cost=20, slippage=0.05,
    ),
)
PORTFOLIO = EquityPortfolioConfig(
    initial_capital=1_000_000, max_positions=2, allocation_fraction=0.5,
    reserved_holdout_sessions=20,
)


def test_shared_portfolio_reserves_tail_and_never_reads_it():
    specs = {symbol: EquityInstrument(symbol=symbol) for symbol in ("AAA", "BBB")}
    first = evaluate_equity_portfolio(
        {"AAA": history("AAA"), "BBB": history("BBB")},
        STRATEGY, PORTFOLIO, specs,
    )
    changed_holdout = evaluate_equity_portfolio(
        {"AAA": history("AAA", 10_000), "BBB": history("BBB", -50)},
        STRATEGY, PORTFOLIO, specs,
    )
    assert first.total_pnl == changed_holdout.total_pnl
    assert first.reserved_holdout_start.isoformat() == "2024-05-10"
    assert first.survivorship_bias_warning


def test_robustness_scenarios_are_declared_not_optimized():
    results = run_robustness_scenarios(
        {"AAA": history("AAA")}, STRATEGY,
        PORTFOLIO.model_copy(update={"max_positions": 1}),
    )
    assert set(results) == {"base", "double_slippage", "double_cost", "combined_stress"}
    assert results["combined_stress"].transaction_costs >= results["base"].transaction_costs


def test_future_current_snapshot_cannot_be_claimed_point_in_time():
    members = [UniverseMember(
        as_of=datetime(2026, 1, 1).date(), index_name="NIFTY 50", symbol="AAA",
    )]
    with __import__("pytest").raises(ValueError, match="first snapshot"):
        evaluate_equity_portfolio(
            {"AAA": history("AAA")}, STRATEGY,
            PORTFOLIO.model_copy(update={"max_positions": 1}),
            universe_members=members, point_in_time_membership=True,
        )
