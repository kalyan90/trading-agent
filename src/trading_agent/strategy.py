from enum import Enum

from pydantic import (
    BaseModel,
    Field,
)

from trading_agent.features import (
    MarketFeatures,
)


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Signal(BaseModel):
    action: Action

    confidence: float = Field(
        ge=0,
        le=1,
    )
    reason: str


# =====================================================
# V1
# =====================================================


def generate_signal(
    price_change: float,
) -> Signal:
    """
    Original basic price-direction strategy.
    """

    if price_change > 0:

        return Signal(
            action=Action.BUY,
            confidence=0.7,
            reason="Price increased",
        )

    if price_change < 0:

        return Signal(
            action=Action.SELL,
            confidence=0.7,
            reason="Price decreased",
        )

    return Signal(
        action=Action.HOLD,
        confidence=0.5,
        reason="Price did not change",
    )


def generate_sma_signal(
    price: float,
    sma: float | None,
) -> Signal:
    """
    V1 SMA strategy.
    """

    if price > sma:

        return Signal(
            action=Action.BUY,
            confidence=0.7,
            reason="Price is above SMA",
        )

    if price < sma:

        return Signal(
            action=Action.SELL,
            confidence=0.7,
            reason="Price is below SMA",
        )

    return Signal(
        action=Action.HOLD,
        confidence=0.5,
        reason="Price is equal to SMA",
    )


def generate_crossover_signal(
    previous_close: float,

    previous_sma: float,

    current_close: float,

    current_sma: float,
) -> Signal:
    """
    V1 price/SMA crossover strategy.
    """

    crossed_above = (
        previous_close
        <= previous_sma

        and

        current_close
        > current_sma
    )

    crossed_below = (
        previous_close
        >= previous_sma

        and

        current_close
        < current_sma
    )

    if crossed_above:

        return Signal(
            action=Action.BUY,
            confidence=0.8,
            reason="Price crossed above SMA",
        )

    if crossed_below:

        return Signal(
            action=Action.SELL,
            confidence=0.8,
            reason="Price crossed below SMA",
        )

    return Signal(
        action=Action.HOLD,
        confidence=0.5,
        reason="No SMA crossover",
    )


# =====================================================
# V2
# =====================================================


def generate_trend_momentum_signal(
    features: MarketFeatures,
) -> Signal:
    """
    V2 deterministic Trend + Momentum strategy.

    Trend:
        fast SMA vs slow SMA

    Momentum:
        RSI
        MACD

    Volatility:
        ATR is calculated and carried in the
        feature model, but it does NOT yet
        influence the decision.

    We will introduce ATR-based risk logic
    separately rather than mixing everything
    into the first strategy.
    """

    # -------------------------------------------------
    # Warm-up / incomplete feature state
    # -------------------------------------------------

    required_features = (
        features.sma_fast,
        features.sma_slow,
        features.rsi,
        features.macd,
        features.macd_signal,
    )

    if any(
        value is None
        for value in required_features
    ):

        return Signal(
            action=Action.HOLD,
            confidence=0,
            reason="Indicator warm-up incomplete",
        )

    # Pydantic/Python now know logically these values
    # are available, but keeping local names makes
    # the rules easier to read.

    sma_fast = (
        features.sma_fast
    )

    sma_slow = (
        features.sma_slow
    )

    rsi = (
        features.rsi
    )

    macd = (
        features.macd
    )

    macd_signal = (
        features.macd_signal
    )

    # =================================================
    # BUY
    # =================================================
    #
    # Trend:
    #     fast SMA > slow SMA
    #
    # Momentum:
    #     MACD above signal
    #
    # Avoid chasing extremely overbought market:
    #     RSI < 70
    #
    # Also require RSI > 50 so momentum is
    # positively biased.
    # =================================================

    bullish_trend = (
        sma_fast
        > sma_slow
    )

    positive_momentum = (
        macd
        > macd_signal
    )

    healthy_rsi = (
        50
        < rsi
        < 70
    )

    if (
        bullish_trend

        and positive_momentum

        and healthy_rsi
    ):

        return Signal(
            action=Action.BUY,
            confidence=0.85,
            reason="Bullish trend and momentum",
        )

    # =================================================
    # SELL
    # =================================================
    #
    # Exit when either:
    #
    # trend breaks
    #
    # OR
    #
    # MACD momentum becomes negative.
    # =================================================

    bearish_trend = (
        sma_fast
        < sma_slow
    )

    negative_momentum = (
        macd
        < macd_signal
    )

    if (
        bearish_trend

        or negative_momentum
    ):

        return Signal(
            action=Action.SELL,
            confidence=0.85,
            reason="Trend or momentum break",
        )

    # =================================================
    # HOLD
    # =================================================

    return Signal(
        action=Action.HOLD,
        confidence=0.5,
        reason="No trend-momentum trigger",
    )
