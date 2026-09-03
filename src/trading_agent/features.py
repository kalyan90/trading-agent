from pydantic import BaseModel

from trading_agent.indicators import (
    calculate_atr,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
)


class MarketFeatures(BaseModel):
    close: float

    sma_fast: float | None
    sma_slow: float | None

    rsi: float | None

    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None

    atr: float | None


def safe_calculate_sma(
    prices: list[float],
    period: int,
) -> float | None:
    """
    V1 calculate_sma intentionally raises when
    there is insufficient history.

    Feature construction is different:
    an unavailable indicator is a valid state,
    represented as None.
    """

    if len(prices) < period:
        return None

    return calculate_sma(
        prices,
        period,
    )


def build_market_features(
    market_data,

    fast_sma_period: int = 20,

    slow_sma_period: int = 50,

    rsi_period: int = 14,

    macd_fast_period: int = 12,

    macd_slow_period: int = 26,

    macd_signal_period: int = 9,

    atr_period: int = 14,
) -> MarketFeatures:

    if not market_data:
        raise ValueError(
            "market_data cannot be empty"
        )

    prices = [
        market.close
        for market in market_data
    ]

    sma_fast = (
        safe_calculate_sma(
            prices,
            fast_sma_period,
        )
    )

    sma_slow = (
        safe_calculate_sma(
            prices,
            slow_sma_period,
        )
    )

    rsi = (
        calculate_rsi(
            prices,
            rsi_period,
        )
    )

    (
        macd,
        macd_signal,
        macd_histogram,
    ) = (
        calculate_macd(
            prices,

            fast_period=(
                macd_fast_period
            ),

            slow_period=(
                macd_slow_period
            ),

            signal_period=(
                macd_signal_period
            ),
        )
    )

    atr = (
        calculate_atr(
            market_data,
            atr_period,
        )
    )

    return MarketFeatures(
        close=(
            market_data[-1].close
        ),

        sma_fast=(
            sma_fast
        ),

        sma_slow=(
            sma_slow
        ),

        rsi=(
            rsi
        ),

        macd=(
            macd
        ),

        macd_signal=(
            macd_signal
        ),

        macd_histogram=(
            macd_histogram
        ),

        atr=(
            atr
        ),
    )