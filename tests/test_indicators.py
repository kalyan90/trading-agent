import pytest

from trading_agent.signals.indicators import calculate_sma


def test_calculate_sma():
    prices = [10, 20, 30]

    sma = calculate_sma(prices, 3)

    assert sma == 20


def test_calculate_sma_with_more_prices():
    prices = [10, 20, 30, 40]

    sma = calculate_sma(prices, 3)

    assert sma == 30


def test_calculate_sma_requires_enough_prices():
    prices = [10, 20]

    with pytest.raises(ValueError):
        calculate_sma(prices, 3)