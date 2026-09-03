"""Portfolio state models."""

from pydantic import BaseModel


class Portfolio(BaseModel):
    initial_capital: float
    cash: float
    position: int = 0

    def buy(self, price: float, quantity: int, transaction_cost: float = 0):
        self.cash -= (price * quantity) + transaction_cost
        self.position += quantity

    def sell(self, price: float, quantity: int, transaction_cost: float = 0):
        self.cash += (price * quantity) - transaction_cost
        self.position -= quantity

    def equity(self, current_price: float) -> float:
        return self.cash + (self.position * current_price)
