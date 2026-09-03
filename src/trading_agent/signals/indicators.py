"""Deterministic technical indicators."""


def calculate_sma(
    prices: list[float],
    period: int,
) -> float:
    """
    Calculate Simple Moving Average.

    Existing V1 contract:
    raise ValueError when there is not enough data.
    """

    if period <= 0:
        raise ValueError(
            "period must be greater than 0"
        )

    if len(prices) < period:
        raise ValueError(
            "Not enough prices to calculate SMA"
        )

    recent_prices = (
        prices[-period:]
    )

    return (
        sum(recent_prices)
        / period
    )


# =====================================================
# EMA
# =====================================================


def calculate_ema_series(
    prices: list[float],
    period: int,
) -> list[float]:
    """
    Calculate an EMA value for every price.
    """

    if period <= 0:
        raise ValueError(
            "period must be greater than 0"
        )

    if not prices:
        return []

    multiplier = (
        2
        / (period + 1)
    )

    ema_values = [
        prices[0]
    ]

    for price in prices[1:]:

        previous_ema = (
            ema_values[-1]
        )

        current_ema = (
            price
            * multiplier
            +
            previous_ema
            * (
                1
                - multiplier
            )
        )

        ema_values.append(
            current_ema
        )

    return ema_values


def calculate_ema(
    prices: list[float],
    period: int,
) -> float | None:

    if period <= 0:
        raise ValueError(
            "period must be greater than 0"
        )

    if len(prices) < period:
        return None

    ema_values = (
        calculate_ema_series(
            prices,
            period,
        )
    )

    return ema_values[-1]


# =====================================================
# RSI
# =====================================================


def calculate_rsi(
    prices: list[float],
    period: int = 14,
) -> float | None:

    if period <= 0:
        raise ValueError(
            "period must be greater than 0"
        )

    if len(prices) < (
        period + 1
    ):
        return None

    recent_prices = (
        prices[
            -(period + 1):
        ]
    )

    gains = []
    losses = []

    for index in range(
        1,
        len(recent_prices),
    ):

        change = (
            recent_prices[index]
            - recent_prices[
                index - 1
            ]
        )

        if change > 0:

            gains.append(
                change
            )

            losses.append(
                0
            )

        elif change < 0:

            gains.append(
                0
            )

            losses.append(
                abs(change)
            )

        else:

            gains.append(
                0
            )

            losses.append(
                0
            )

    average_gain = (
        sum(gains)
        / period
    )

    average_loss = (
        sum(losses)
        / period
    )

    if average_loss == 0:

        if average_gain == 0:
            return 50

        return 100

    relative_strength = (
        average_gain
        / average_loss
    )

    return (
        100
        - (
            100
            / (
                1
                + relative_strength
            )
        )
    )


# =====================================================
# MACD
# =====================================================


def calculate_macd(
    prices: list[float],

    fast_period: int = 12,

    slow_period: int = 26,

    signal_period: int = 9,
) -> tuple[
    float | None,
    float | None,
    float | None,
]:

    if (
        fast_period <= 0
        or slow_period <= 0
        or signal_period <= 0
    ):
        raise ValueError(
            "MACD periods must be greater than 0"
        )

    if fast_period >= slow_period:
        raise ValueError(
            "fast_period must be smaller "
            "than slow_period"
        )

    minimum_prices = (
        slow_period
        + signal_period
        - 1
    )

    if len(prices) < minimum_prices:
        return (
            None,
            None,
            None,
        )

    fast_ema_series = (
        calculate_ema_series(
            prices,
            fast_period,
        )
    )

    slow_ema_series = (
        calculate_ema_series(
            prices,
            slow_period,
        )
    )

    macd_series = []

    for index in range(
        slow_period - 1,
        len(prices),
    ):

        macd_value = (
            fast_ema_series[index]
            - slow_ema_series[index]
        )

        macd_series.append(
            macd_value
        )

    if len(macd_series) < signal_period:
        return (
            None,
            None,
            None,
        )

    signal_series = (
        calculate_ema_series(
            macd_series,
            signal_period,
        )
    )

    macd = (
        macd_series[-1]
    )

    signal = (
        signal_series[-1]
    )

    histogram = (
        macd
        - signal
    )

    return (
        macd,
        signal,
        histogram,
    )


# =====================================================
# ATR
# =====================================================


def calculate_atr(
    market_data,
    period: int = 14,
) -> float | None:

    if period <= 0:
        raise ValueError(
            "period must be greater than 0"
        )

    if len(market_data) < (
        period + 1
    ):
        return None

    relevant_data = (
        market_data[
            -(period + 1):
        ]
    )

    true_ranges = []

    for index in range(
        1,
        len(relevant_data),
    ):

        market = (
            relevant_data[index]
        )

        previous_market = (
            relevant_data[
                index - 1
            ]
        )

        high_low = (
            market.high
            - market.low
        )

        high_previous_close = abs(
            market.high
            - previous_market.close
        )

        low_previous_close = abs(
            market.low
            - previous_market.close
        )

        true_range = max(
            high_low,
            high_previous_close,
            low_previous_close,
        )

        true_ranges.append(
            true_range
        )

    return (
        sum(true_ranges)
        / period
    )
