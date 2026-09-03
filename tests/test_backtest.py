from trading_agent.research.backtest import (
    calculate_buy_price,
    calculate_sell_price,
)


def test_buy_slippage():

    price = calculate_buy_price(
        market_price=100,
        slippage=2,
    )

    assert price == 102


def test_sell_slippage():

    price = calculate_sell_price(
        market_price=100,
        slippage=2,
    )

    assert price == 98