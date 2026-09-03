from datetime import datetime, timedelta
from types import SimpleNamespace

import trading_agent.continuous as continuous
from trading_agent.config import V2_CONFIG
from trading_agent.market import MarketData
from trading_agent.strategy import Action, Signal


def data(size):
    start = datetime(2020, 1, 1)
    return [MarketData(
        date=start + timedelta(days=index), symbol="NIFTY",
        open=100 + index, high=102 + index, low=98 + index,
        close=100 + index, volume=1000,
    ) for index in range(size)]


def result(pnl, trades):
    return SimpleNamespace(trades=trades, total_pnl=pnl)


def test_rejected_window_forces_boundary_liquidation(monkeypatch):
    calls = 0
    dummy_trades = [object()] * 5

    def gated(*args, **kwargs):
        nonlocal calls
        calls += 1
        return result(1 if calls == 1 else 0, dummy_trades if calls == 1 else [])

    monkeypatch.setattr(continuous, "run_backtest", gated)
    monkeypatch.setattr(
        continuous, "generate_trend_momentum_signal",
        lambda features: Signal(action=Action.BUY, confidence=1, reason="test"),
    )
    config = V2_CONFIG.model_copy(update={"train_size": 50, "test_size": 5})
    output = continuous.evaluate_continuous_v3(data(60), config)

    assert output.accepted_windows == 1
    assert output.rejected_windows == 1
    assert output.gate_liquidations == 1
    assert output.trades[0].exit_date == data(60)[55].date
