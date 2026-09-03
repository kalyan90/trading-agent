from trading_agent.portfolio import Portfolio


def test_buy_with_quantity():

    portfolio = Portfolio(
        initial_capital=100000,
        cash=100000,
    )

    portfolio.buy(
        price=100,
        quantity=5,
        transaction_cost=10,
    )

    assert portfolio.position == 5

    assert portfolio.cash == (
        100000
        - 500
        - 10
    )


def test_sell_with_quantity():

    portfolio = Portfolio(
        initial_capital=100000,
        cash=100000,
    )

    portfolio.buy(
        price=100,
        quantity=5,
        transaction_cost=10,
    )

    portfolio.sell(
        price=110,
        quantity=5,
        transaction_cost=10,
    )

    assert portfolio.position == 0

    assert portfolio.cash == 100030


def test_equity_includes_open_position():

    portfolio = Portfolio(
        initial_capital=100000,
        cash=100000,
    )

    portfolio.buy(
        price=100,
        quantity=5,
        transaction_cost=10,
    )

    equity = portfolio.equity(
        current_price=120
    )

    assert equity == 100090