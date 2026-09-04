from decimal import Decimal

from trading_agent.core.fees import (
    CashEquityFeeSchedule, OrderSide, calculate_cash_equity_fees,
)


def test_delivery_fee_side_applicability_and_gst_base():
    schedule = CashEquityFeeSchedule()
    buy = calculate_cash_equity_fees(100, 100, OrderSide.BUY, schedule)
    sell = calculate_cash_equity_fees(100, 100, OrderSide.SELL, schedule)
    assert buy.turnover == Decimal("10000.00")
    assert buy.stt == sell.stt == Decimal("10.00")
    assert buy.stamp_duty == Decimal("1.50")
    assert sell.stamp_duty == Decimal("0.00")
    assert buy.gst == Decimal("0.06")  # excludes STT and stamp duty
    assert buy.total == Decimal("11.88")
    assert sell.total == Decimal("10.38")


def test_brokerage_is_configurable_capped_assumption():
    schedule = CashEquityFeeSchedule(
        brokerage_rate=Decimal("0.001"), brokerage_cap=Decimal("20"),
        brokerage_assumption="test broker plan",
    )
    fees = calculate_cash_equity_fees(1000, 100, OrderSide.BUY, schedule)
    assert fees.brokerage == Decimal("20.00")
    assert fees.gst == Decimal("4.17")


def test_fee_multiplier_stresses_every_component_and_total():
    base = calculate_cash_equity_fees(100, 100, OrderSide.SELL, CashEquityFeeSchedule())
    stress = calculate_cash_equity_fees(
        100, 100, OrderSide.SELL, CashEquityFeeSchedule(fee_multiplier=Decimal("2")),
    )
    assert stress.total == base.total * 2
