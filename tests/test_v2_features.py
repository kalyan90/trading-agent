from datetime import datetime, timedelta

from trading_agent.signals.features import (
    MarketFeatures,
    build_market_features,
)

from trading_agent.signals.indicators import (
    calculate_atr,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
)

from trading_agent.core.market import (
    MarketData,
)

from trading_agent.signals.strategy import (
    Action,
    generate_trend_momentum_signal,
)


def create_market_data(
    closes: list[float],
):

    start_date = datetime(
        2026,
        1,
        1,
    )

    market_data = []

    for index, close in enumerate(
        closes
    ):

        market_data.append(
            MarketData(
                symbol="NIFTY",

                date=(
                    start_date
                    + timedelta(
                        days=index
                    )
                ),

                open=(
                    close - 1
                ),

                high=(
                    close + 2
                ),

                low=(
                    close - 2
                ),

                close=close,

                volume=1000,
            )
        )

    return market_data


# =====================================================
# SMA
# =====================================================


def test_sma():

    prices = [
        1,
        2,
        3,
        4,
        5,
    ]

    assert (
        calculate_sma(
            prices,
            3,
        )
        == 4
    )

import pytest

def test_sma_requires_enough_data():

    with pytest.raises(
        ValueError
    ):
        calculate_sma(
            [1, 2],
            3,
        )


# =====================================================
# EMA
# =====================================================


def test_ema_returns_value():

    prices = list(
        range(
            1,
            21,
        )
    )

    ema = (
        calculate_ema(
            prices,
            10,
        )
    )

    assert ema is not None

    assert ema > 0


# =====================================================
# RSI
# =====================================================


def test_rsi_rising_market():

    prices = list(
        range(
            1,
            20,
        )
    )

    rsi = (
        calculate_rsi(
            prices,
            14,
        )
    )

    assert rsi == 100


def test_rsi_falling_market():

    prices = list(
        range(
            20,
            1,
            -1,
        )
    )

    rsi = (
        calculate_rsi(
            prices,
            14,
        )
    )

    assert rsi == 0


def test_rsi_requires_enough_data():

    assert (
        calculate_rsi(
            [1, 2, 3],
            14,
        )
        is None
    )


# =====================================================
# MACD
# =====================================================


def test_macd_returns_values():

    prices = [
        float(value)
        for value in range(
            1,
            50,
        )
    ]

    (
        macd,
        signal,
        histogram,
    ) = (
        calculate_macd(
            prices
        )
    )

    assert macd is not None

    assert signal is not None

    assert histogram is not None


def test_macd_requires_warmup():

    (
        macd,
        signal,
        histogram,
    ) = (
        calculate_macd(
            [
                1,
                2,
                3,
            ]
        )
    )

    assert macd is None
    assert signal is None
    assert histogram is None


# =====================================================
# ATR
# =====================================================


def test_atr_returns_positive_value():

    market_data = (
        create_market_data(
            [
                float(value)
                for value in range(
                    100,
                    120,
                )
            ]
        )
    )

    atr = (
        calculate_atr(
            market_data,
            14,
        )
    )

    assert atr is not None

    assert atr > 0


# =====================================================
# Feature builder
# =====================================================


def test_feature_builder():

    market_data = (
        create_market_data(
            [
                float(value)
                for value in range(
                    100,
                    170,
                )
            ]
        )
    )

    features = (
        build_market_features(
            market_data
        )
    )

    assert (
        features.close
        == 169
    )

    assert (
        features.sma_fast
        is not None
    )

    assert (
        features.sma_slow
        is not None
    )

    assert (
        features.rsi
        is not None
    )

    assert (
        features.macd
        is not None
    )

    assert (
        features.macd_signal
        is not None
    )

    assert (
        features.atr
        is not None
    )


def test_feature_builder_preserves_warmup():

    market_data = (
        create_market_data(
            [
                100,
                101,
                102,
            ]
        )
    )

    features = (
        build_market_features(
            market_data
        )
    )

    assert (
        features.sma_fast
        is None
    )

    assert (
        features.sma_slow
        is None
    )

    assert (
        features.rsi
        is None
    )


# =====================================================
# Trend Momentum strategy
# =====================================================


def test_trend_momentum_buy():

    features = MarketFeatures(
        close=100,

        sma_fast=105,

        sma_slow=100,

        rsi=60,

        macd=2,

        macd_signal=1,

        macd_histogram=1,

        atr=3,
    )

    signal = (
        generate_trend_momentum_signal(
            features
        )
    )

    assert (
        signal.action
        == Action.BUY
    )


def test_trend_momentum_sell_when_trend_breaks():

    features = MarketFeatures(
        close=100,

        sma_fast=95,

        sma_slow=100,

        rsi=45,

        macd=2,

        macd_signal=1,

        macd_histogram=1,

        atr=3,
    )

    signal = (
        generate_trend_momentum_signal(
            features
        )
    )

    assert (
        signal.action
        == Action.SELL
    )


def test_trend_momentum_sell_when_macd_breaks():

    features = MarketFeatures(
        close=100,

        sma_fast=105,

        sma_slow=100,

        rsi=60,

        macd=1,

        macd_signal=2,

        macd_histogram=-1,

        atr=3,
    )

    signal = (
        generate_trend_momentum_signal(
            features
        )
    )

    assert (
        signal.action
        == Action.SELL
    )


def test_trend_momentum_does_not_buy_overbought():

    features = MarketFeatures(
        close=100,

        sma_fast=105,

        sma_slow=100,

        rsi=75,

        macd=2,

        macd_signal=1,

        macd_histogram=1,

        atr=3,
    )

    signal = (
        generate_trend_momentum_signal(
            features
        )
    )

    assert (
        signal.action
        == Action.HOLD
    )


def test_trend_momentum_holds_during_warmup():

    features = MarketFeatures(
        close=100,

        sma_fast=None,

        sma_slow=None,

        rsi=None,

        macd=None,

        macd_signal=None,

        macd_histogram=None,

        atr=None,
    )

    signal = (
        generate_trend_momentum_signal(
            features
        )
    )

    assert (
        signal.action
        == Action.HOLD
    )