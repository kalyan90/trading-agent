"""Run the frozen signal policy independently across a stock universe."""

from pydantic import BaseModel

from trading_agent.core.config import V2Config
from trading_agent.research.experiment import (
    create_walk_forward_windows, evaluate_v2_system,
)


class StockResearchResult(BaseModel):
    symbol: str
    observations: int
    windows: int
    accepted_windows: int
    total_oos_pnl: float
    total_oos_trades: int
    benchmark_pnl: float
    excess_pnl: float


def evaluate_stock_universe(data_by_symbol, config: V2Config):
    results = []
    for symbol, market_data in sorted(data_by_symbol.items()):
        if len(market_data) < config.train_size + config.test_size:
            continue
        symbol_config = config.model_copy(update={"symbol": symbol})
        windows = create_walk_forward_windows(
            market_data, train_size=config.train_size, test_size=config.test_size,
        )
        _, summary = evaluate_v2_system(windows, symbol_config)
        results.append(StockResearchResult(
            symbol=symbol, observations=len(market_data),
            windows=summary.total_windows,
            accepted_windows=summary.accepted_windows,
            total_oos_pnl=summary.total_oos_pnl,
            total_oos_trades=summary.total_oos_trades,
            benchmark_pnl=summary.total_benchmark_pnl,
            excess_pnl=summary.total_excess_pnl,
        ))
    return results
