"""Spot-market domain models."""

from pydantic import BaseModel
from datetime import datetime

class MarketData(BaseModel):
    date: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None

    def price_change(self):
        return self.close - self.open

    def price_change_percent(self):
        return ((self.close - self.open) / self.open) * 100
