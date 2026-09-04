import math
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from trading_agent.core.config import ExecutionConfig, V2Config
from trading_agent.core.dividends import DividendEvent
from trading_agent.core.equity import EquityPortfolioConfig
from trading_agent.core.fees import CashEquityFeeSchedule
from trading_agent.core.market import MarketData
from trading_agent.core.universe import UniverseMember
from trading_agent.research.dynamic_equity_portfolio import evaluate_dynamic_equity_portfolio


def history(symbol, start, count, holdout_delta=0):
    rows = []
    for i in range(count):
        day = start + timedelta(days=i)
        close = 100 + i * 0.1 + math.sin(i / 3) * 7
        if day >= date(2025, 9, 1):
            close += holdout_delta
        rows.append(MarketData(
            date=datetime.combine(day, datetime.min.time()), symbol=symbol,
            open=close - .1, high=close + 1, low=close - 1, close=close,
            volume=500_000,
        ))
    return rows


STRATEGY = V2Config(
    train_size=40, test_size=10, fast_sma_period=5, slow_sma_period=10,
    rsi_period=5, macd_fast_period=4, macd_slow_period=8,
    macd_signal_period=3, atr_period=5, minimum_train_trades=1,
    execution=ExecutionConfig(
        initial_capital=100_000, position_size=1, transaction_cost=0, slippage=.05,
    ),
)
PORTFOLIO = EquityPortfolioConfig(
    reserved_holdout_sessions=250,
    fee_schedule=CashEquityFeeSchedule(), transaction_cost=0,
)


def run(data, **kwargs):
    return evaluate_dynamic_equity_portfolio(
        data, STRATEGY, PORTFOLIO, development_start=date(2024, 1, 1),
        development_end=date(2024, 8, 1), retrospective_static_membership=True,
        **kwargs,
    )


def test_late_listing_does_not_truncate_union_calendar():
    base = history("OLD", date(2023, 1, 1), 700)
    late = history("NEW", date(2024, 6, 1), 100)
    single = run({"OLD": base})
    combined = run({"OLD": base, "NEW": late})
    assert combined.calendar_start == single.calendar_start == date(2024, 1, 1)
    assert combined.calendar_end == single.calendar_end == date(2024, 8, 1)
    assert combined.sessions == single.sessions


def test_missing_symbol_sessions_do_not_remove_exchange_sessions():
    old = history("OLD", date(2023, 1, 1), 700)
    sparse = history("SPARSE", date(2023, 1, 1), 700)[::3]
    result = run({"OLD": old, "SPARSE": sparse})
    assert result.sessions == 214


def test_reserved_tail_is_never_read():
    first = history("OLD", date(2023, 1, 1), 1100)
    changed = history("OLD", date(2023, 1, 1), 1100, 10000)
    assert run({"OLD": first}).total_pnl == run({"OLD": changed}).total_pnl


def test_future_membership_snapshot_requires_explicit_retrospective_mode():
    members = [UniverseMember(
        as_of=date(2026, 1, 1), index_name="NIFTY 50", symbol="OLD",
    )]
    with pytest.raises(ValueError, match="explicit retrospective"):
        evaluate_dynamic_equity_portfolio(
            {"OLD": history("OLD", date(2023, 1, 1), 700)}, STRATEGY, PORTFOLIO,
            development_start=date(2024, 1, 1), development_end=date(2024, 8, 1),
            universe_members=members,
        )


def test_cohort_results_retain_exact_declared_dates():
    data = {"OLD": history("OLD", date(2019, 1, 1), 2200)}
    for start, end in ((date(2020, 1, 1), date(2021, 12, 31)),
                       (date(2022, 1, 1), date(2023, 12, 31))):
        result = evaluate_dynamic_equity_portfolio(
            data, STRATEGY, PORTFOLIO, development_start=start,
            development_end=end, retrospective_static_membership=True,
        )
        assert result.calendar_start == start
        assert result.calendar_end == end


def test_optional_dividend_interface_and_authority_validation():
    data = {"OLD": history("OLD", date(2023, 1, 1), 700)}
    price_only = run(data)
    event = DividendEvent(
        symbol="OLD", ex_date=date(2024, 2, 1), cash_per_share=2,
        source="NSE corporate actions", source_url="https://www.nseindia.com/",
    )
    total_return = run(data, dividends=[event])
    assert price_only.price_return_benchmark_only
    assert not total_return.price_return_benchmark_only
    assert total_return.benchmark_dividend_cash >= 0
    with pytest.raises(ValueError, match="source URL"):
        DividendEvent.model_construct(
            symbol="OLD", ex_date=date(2024, 2, 1), cash_per_share=2,
            source="unknown", source_url="", verified=True,
        )
        run(data, dividends=[DividendEvent.model_construct(
            symbol="OLD", ex_date=date(2024, 2, 1), cash_per_share=2,
            source="unknown", source_url="", verified=True,
        )])


def test_dp_charge_is_sell_only_and_configurable():
    from trading_agent.core.fees import OrderSide, calculate_cash_equity_fees
    schedule = CashEquityFeeSchedule(dp_charge_per_sell=Decimal("15.50"))
    buy = calculate_cash_equity_fees(100, 10, OrderSide.BUY, schedule)
    sell = calculate_cash_equity_fees(100, 10, OrderSide.SELL, schedule)
    assert buy.dp_charge == Decimal("0.00")
    assert sell.dp_charge == Decimal("15.50")
    assert sell.total - buy.total == Decimal("15.35")  # DP less buy-only stamp
