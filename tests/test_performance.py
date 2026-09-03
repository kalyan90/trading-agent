from trading_agent.performance import (
    calculate_win_loss,
    calculate_win_rate,
    calculate_average_profit,
    calculate_max_drawdown,
)


def test_win_rate():
    result = calculate_win_rate(10, 6)

    assert result == 60

def test_win_loss():
    # We can use simple mock-like objects for now
    class TestTrade:
        def __init__(self, profit):
            self.profit = profit

    trades = [
        TestTrade(100),
        TestTrade(-50),
        TestTrade(200),
        TestTrade(-25),
    ]

    winning, losing = calculate_win_loss(trades)

    assert winning == 2
    assert losing == 2


def test_average_profit():
    result = calculate_average_profit(300, 3)

    assert result == 100


def test_max_drawdown():
    profit_history = [100, 250, 150, 50]

    result = calculate_max_drawdown(profit_history)

    assert result == 200