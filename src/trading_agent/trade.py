from datetime import datetime

from pydantic import BaseModel


class Trade(BaseModel):
    entry_date: datetime
    entry_price: float

    exit_date: datetime
    exit_price: float

    profit: float


class BacktestResult(BaseModel):
    trades: list[Trade]

    # =================================================
    # Strategy
    # =================================================

    # Realized P&L from closed trades.
    total_profit: float

    # Complete portfolio P&L including
    # marked-to-market open position.
    total_pnl: float

    winning_trades: int
    losing_trades: int

    win_rate: float
    average_profit: float

    max_drawdown: float

    final_equity: float
    total_return: float

    # P&L divided by max drawdown.
    profit_drawdown_ratio: float

    # =================================================
    # Exposure
    # =================================================

    exposure_percent: float

    # =================================================
    # Benchmark
    # =================================================

    benchmark_pnl: float
    benchmark_return: float

    benchmark_max_drawdown: float

    benchmark_profit_drawdown_ratio: float

    # =================================================
    # Relative performance
    # =================================================

    excess_pnl: float
    excess_return: float