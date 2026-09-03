"""Daily-settled futures account with explicit margin and charge models."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FuturesMarginConfig(BaseModel):
    """Transparent margin proxy until dated NSE SPAN files are integrated."""

    model_config = ConfigDict(frozen=True)

    initial_margin_rate: float = Field(default=0.15, gt=0, le=1)
    maintenance_margin_rate: float = Field(default=0.12, gt=0, le=1)

    @model_validator(mode="after")
    def maintenance_does_not_exceed_initial(self):
        if self.maintenance_margin_rate > self.initial_margin_rate:
            raise ValueError("maintenance margin cannot exceed initial margin")
        return self


class FuturesChargeConfig(BaseModel):
    """Retail charge assumptions plus dated statutory futures levies."""

    model_config = ConfigDict(frozen=True)

    brokerage_per_order: float = Field(default=20, ge=0)
    exchange_transaction_rate: float = Field(default=0.0000183, ge=0)
    sebi_turnover_rate: float = Field(default=0.000001, ge=0)
    stamp_duty_buy_rate: float = Field(default=0.00002, ge=0)
    gst_rate: float = Field(default=0.18, ge=0)

    def stt_sell_rate(self, trade_date: date) -> float:
        if trade_date >= date(2024, 10, 1):
            return 0.0002
        if trade_date >= date(2023, 4, 1):
            return 0.000125
        return 0.0001

    def order_charge(self, trade_date: date, price: float, lot: int,
                     is_buy: bool) -> float:
        turnover = price * lot
        exchange = turnover * self.exchange_transaction_rate
        sebi = turnover * self.sebi_turnover_rate
        stamp = turnover * self.stamp_duty_buy_rate if is_buy else 0
        stt = 0 if is_buy else turnover * self.stt_sell_rate(trade_date)
        gst = (self.brokerage_per_order + exchange + sebi) * self.gst_rate
        return self.brokerage_per_order + exchange + sebi + stamp + stt + gst


class FuturesAccount:
    def __init__(self, initial_cash: float, transaction_cost: float,
                 margin: FuturesMarginConfig | None = None,
                 charges: FuturesChargeConfig | None = None):
        self.cash = initial_cash
        self.transaction_cost = transaction_cost
        self.margin = margin
        self.charges = charges
        self.reference_price: float | None = None
        self.lot = 0
        self.peak_margin = 0.0
        self.minimum_free_cash = initial_cash
        self.total_charges = 0.0

    def _order_charge(self, trade_date: date | None, price: float,
                      lot: int, is_buy: bool) -> float:
        if self.charges is None:
            return self.transaction_cost / 2
        if trade_date is None:
            raise ValueError("trade_date is required by the detailed charge model")
        return self.charges.order_charge(trade_date, price, lot, is_buy)

    @property
    def is_open(self) -> bool:
        return self.reference_price is not None

    def required_margin(self, price: float, maintenance: bool = False) -> float:
        if self.margin is None or not self.lot:
            return 0.0
        rate = (self.margin.maintenance_margin_rate if maintenance
                else self.margin.initial_margin_rate)
        return price * self.lot * rate

    def open(self, price: float, lot: int, trade_date: date | None = None) -> bool:
        if self.is_open:
            raise ValueError("A futures position is already open")
        required = 0.0 if self.margin is None else price * lot * self.margin.initial_margin_rate
        charge = self._order_charge(trade_date, price, lot, is_buy=True)
        if self.cash - charge < required:
            return False
        self.cash -= charge
        self.total_charges += charge
        self.reference_price = price
        self.lot = lot
        self.peak_margin = max(self.peak_margin, required)
        self.minimum_free_cash = min(self.minimum_free_cash, self.cash - required)
        return True

    def settle(self, settlement_price: float) -> bool:
        """Credit daily variation P&L and report a maintenance-margin breach."""
        if not self.is_open:
            return False
        self.cash += (settlement_price - self.reference_price) * self.lot
        self.reference_price = settlement_price
        initial = self.required_margin(settlement_price)
        maintenance = self.required_margin(settlement_price, maintenance=True)
        self.peak_margin = max(self.peak_margin, initial)
        self.minimum_free_cash = min(self.minimum_free_cash, self.cash - initial)
        return self.margin is not None and self.cash < maintenance

    def close(self, price: float, trade_date: date | None = None) -> None:
        if not self.is_open:
            raise ValueError("No futures position is open")
        self.cash += (price - self.reference_price) * self.lot
        charge = self._order_charge(trade_date, price, self.lot, is_buy=False)
        self.cash -= charge
        self.total_charges += charge
        self.reference_price = None
        self.lot = 0
