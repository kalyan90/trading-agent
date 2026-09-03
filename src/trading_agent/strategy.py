from enum import Enum
from pydantic import BaseModel, Field

class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class Signal(BaseModel):
    action: Action
    confidence: float = Field(ge=0, le=1)
    reason: str


def generate_signal(price_change: float) -> Signal:
    if price_change > 0:
        return Signal(
            action=Action.BUY,
            confidence=0.7,
            reason="Price increased"
        )
    elif price_change < 0:
        return Signal(
            action=Action.SELL,
            confidence=0.7,
            reason="Price decreased"
        )
    else:
        return Signal(
            action=Action.HOLD,
            confidence=0.5,
            reason="Price did not change"
        )

def generate_sma_signal(close, sma):
    if close > sma:
        return Signal(
            action=Action.BUY,
            confidence=0.7,
            reason="Price is above SMA"
        )
    elif close < sma:
        return Signal(
            action=Action.SELL,
            confidence=0.7,
            reason="Price is below SMA"
        )
    else:
        return Signal(
            action=Action.HOLD,
            confidence=0.5,
            reason="Price is equal to SMA"
        )

def generate_crossover_signal(
    previous_close: float,
    previous_sma: float,
    current_close: float,
    current_sma: float,
) -> Signal:

    if previous_close <= previous_sma and current_close > current_sma:
        return Signal(
            action=Action.BUY,
            confidence=0.8,
            reason="Price crossed above SMA",
        )

    elif previous_close >= previous_sma and current_close < current_sma:
        return Signal(
            action=Action.SELL,
            confidence=0.8,
            reason="Price crossed below SMA",
        )

    else:
        return Signal(
            action=Action.HOLD,
            confidence=0.5,
            reason="No SMA crossover",
        )