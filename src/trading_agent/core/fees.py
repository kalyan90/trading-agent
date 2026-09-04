"""Transparent Indian NSE cash-equity delivery fee accounting."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class CashEquityFeeSchedule(BaseModel):
    """Rates are decimal fractions of turnover, not percentages.

    Statutory/exchange rates are verified from the NSE pages named in ``sources``.
    Brokerage is deliberately a user assumption because it varies by broker/plan.
    """

    model_config = ConfigDict(frozen=True)

    name: str = "NSE delivery cash -- 2026-03-01"
    effective_from: date = date(2026, 3, 1)
    brokerage_rate: Decimal = Field(default=Decimal("0"), ge=0)
    brokerage_minimum: Decimal = Field(default=Decimal("0"), ge=0)
    brokerage_cap: Decimal | None = Field(default=None, ge=0)
    stt_rate: Decimal = Decimal("0.001")
    exchange_rate: Decimal = Decimal("0.000030699")
    sebi_rate: Decimal = Decimal("0.000001")
    gst_rate: Decimal = Decimal("0.18")
    stamp_buy_rate: Decimal = Decimal("0.00015")
    fee_multiplier: Decimal = Field(default=Decimal("1"), gt=0)
    brokerage_assumption: str = "zero-brokerage delivery plan; configure for the actual broker"
    sources: tuple[str, ...] = (
        "https://www.nseindia.com/static/invest/first-time-investor-sebi-turnover-fees-stt-other-levies",
        "https://nsearchives.nseindia.com/content/circulars/FA73061.pdf",
    )


class FeeBreakdown(BaseModel):
    model_config = ConfigDict(frozen=True)

    turnover: Decimal
    brokerage: Decimal
    stt: Decimal
    exchange_transaction_charge: Decimal
    sebi_turnover_fee: Decimal
    gst: Decimal
    stamp_duty: Decimal
    total: Decimal


def _paise(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rupee(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def calculate_cash_equity_fees(
    price: float | Decimal, quantity: int, side: OrderSide,
    schedule: CashEquityFeeSchedule,
) -> FeeBreakdown:
    """Calculate one delivery fill; components and total round to paise.

    STT applies to both delivery sides, stamp duty only to buys, and GST applies
    only to brokerage plus exchange and SEBI charges. This intentionally excludes
    DP/depository charges, which are broker/depository-specific assumptions.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    turnover = _paise(Decimal(str(price)) * quantity)
    raw_brokerage = max(turnover * schedule.brokerage_rate, schedule.brokerage_minimum)
    if schedule.brokerage_cap is not None:
        raw_brokerage = min(raw_brokerage, schedule.brokerage_cap)
    brokerage = _paise(raw_brokerage)
    # Statutory STT liability rounds to the nearest rupee (50 paise upward).
    stt = _rupee(turnover * schedule.stt_rate)
    exchange = _paise(turnover * schedule.exchange_rate)
    sebi = _paise(turnover * schedule.sebi_rate)
    gst = _paise((brokerage + exchange + sebi) * schedule.gst_rate)
    stamp = _paise(turnover * schedule.stamp_buy_rate) if side == OrderSide.BUY else Decimal("0.00")
    components = (brokerage, stt, exchange, sebi, gst, stamp)
    multiplier = schedule.fee_multiplier
    total = _paise(sum(components, Decimal("0")) * multiplier)
    return FeeBreakdown(
        turnover=turnover, brokerage=_paise(brokerage * multiplier),
        stt=_paise(stt * multiplier),
        exchange_transaction_charge=_paise(exchange * multiplier),
        sebi_turnover_fee=_paise(sebi * multiplier), gst=_paise(gst * multiplier),
        stamp_duty=_paise(stamp * multiplier), total=total,
    )


V3_STEP5_FEE_SCHEDULE = CashEquityFeeSchedule()
