"""Research performance metrics."""


def calculate_win_loss(trades):
    winning_trades = 0
    losing_trades = 0

    for trade in trades:
        if trade.profit > 0:
            winning_trades += 1
        elif trade.profit < 0:
            losing_trades += 1

    return winning_trades, losing_trades

def calculate_win_rate(trades_len, winning_trades):
    if trades_len > 0:
        win_rate = (winning_trades / trades_len) * 100
    else:
        win_rate = 0
    
    return win_rate

def calculate_average_profit(profit, trades_len):
    if trades_len > 0:
        average_profit = profit / trades_len
    else:
        average_profit = 0
    
    return average_profit

def calculate_max_drawdown(equity_history):
    peak_equity = equity_history[0]
    max_drawdown = 0

    for current_equity in equity_history:
        if current_equity > peak_equity:
            peak_equity = current_equity

        drawdown = peak_equity - current_equity

        if drawdown > max_drawdown:
            max_drawdown = drawdown

    return max_drawdown
