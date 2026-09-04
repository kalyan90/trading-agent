"""Broker-neutral contracts for V3 Step 3; no live adapter is enabled."""

from enum import Enum
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    FILLED = "FILLED"
    REJECTED = "REJECTED"


class OrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    quantity: int = Field(gt=0)
    client_order_id: str


class OrderResult(BaseModel):
    broker_order_id: str
    client_order_id: str
    status: OrderStatus
    fill_price: float | None = None
    reason: str | None = None


class Broker(Protocol):
    def submit(self, order: OrderRequest) -> OrderResult: ...
    def positions(self) -> dict[str, int]: ...
    def available_cash(self) -> float: ...


class PaperBroker:
    """Deterministic, immediate-fill adapter for replay and shadow testing."""

    def __init__(self, initial_cash: float, max_order_value: float):
        self.cash = initial_cash
        self.max_order_value = max_order_value
        self.prices: dict[str, float] = {}
        self._positions: dict[str, int] = {}
        self._orders: dict[str, OrderResult] = {}

    def mark(self, symbol: str, price: float):
        if price <= 0:
            raise ValueError("price must be positive")
        self.prices[symbol] = price

    def submit(self, order: OrderRequest) -> OrderResult:
        if order.client_order_id in self._orders:
            return self._orders[order.client_order_id]
        price = self.prices.get(order.symbol)
        reason = None
        if price is None:
            reason = "missing market price"
        elif price * order.quantity > self.max_order_value:
            reason = "order value exceeds risk limit"
        elif order.side == OrderSide.BUY and price * order.quantity > self.cash:
            reason = "insufficient cash"
        elif order.side == OrderSide.SELL and order.quantity > self._positions.get(order.symbol, 0):
            reason = "insufficient position"
        if reason:
            result = OrderResult(
                broker_order_id=str(uuid4()), client_order_id=order.client_order_id,
                status=OrderStatus.REJECTED, reason=reason,
            )
        else:
            signed = order.quantity if order.side == OrderSide.BUY else -order.quantity
            self.cash -= signed * price
            self._positions[order.symbol] = self._positions.get(order.symbol, 0) + signed
            result = OrderResult(
                broker_order_id=str(uuid4()), client_order_id=order.client_order_id,
                status=OrderStatus.FILLED, fill_price=price,
            )
        self._orders[order.client_order_id] = result
        return result

    def positions(self) -> dict[str, int]:
        return dict(self._positions)

    def available_cash(self) -> float:
        return self.cash
