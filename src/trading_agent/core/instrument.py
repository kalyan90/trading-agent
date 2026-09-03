"""Tradable-instrument metadata."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class FuturesContractSpec(BaseModel):
    """Dated exchange contract metadata, separate from strategy logic."""

    model_config = ConfigDict(frozen=True)

    underlying: str
    exchange_symbol: str
    currency: str = "INR"
    lot_size: int = Field(gt=0)
    point_value: float = Field(gt=0)
    effective_from: date
    source_reference: str

    def notional_value(self, futures_price: float, lots: int = 1) -> float:
        if futures_price <= 0 or lots <= 0:
            raise ValueError("futures_price and lots must be greater than 0")
        return futures_price * self.lot_size * lots

    def monetary_pnl(self, point_change: float, lots: int = 1) -> float:
        if lots <= 0:
            raise ValueError("lots must be greater than 0")
        return point_change * self.point_value * lots


NIFTY_FUTURES_2026 = FuturesContractSpec(
    underlying="NIFTY 50",
    exchange_symbol="NIFTY",
    lot_size=65,
    point_value=65,
    effective_from=date(2026, 1, 27),
    source_reference="NSE/FAOP/70616",
)
