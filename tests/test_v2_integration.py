from datetime import datetime, timedelta

import trading_agent.research.backtest as backtest_module
from trading_agent.research.backtest import run_backtest
from trading_agent.core.config import StrategyType, V1_CONFIG, V2_CONFIG
from trading_agent.research.experiment import (
    create_trading_config,
    create_v2_trading_config,
    diagnose_v2_windows,
    evaluate_v2_system,
)
from trading_agent.core.market import MarketData
from trading_agent.signals.strategy import Action, Signal


def market_data(closes):
    start = datetime(2025, 1, 1)
    return [
        MarketData(
            symbol="NIFTY",
            date=start + timedelta(days=index),
            open=close,
            high=close + 2,
            low=close - 2,
            close=close,
            volume=1000,
        )
        for index, close in enumerate(closes)
    ]


def test_v1_config_conversion_remains_available():
    config = create_trading_config(
        V1_CONFIG, 20, StrategyType.SMA_CROSSOVER
    )
    assert config.strategy == StrategyType.SMA_CROSSOVER
    assert config.sma_period == 20


def test_v2_configuration_is_exact_and_fixed():
    config = create_v2_trading_config(V2_CONFIG)
    assert (config.fast_sma_period, config.slow_sma_period) == (20, 50)
    assert config.rsi_period == 14
    assert (
        config.macd_fast_period,
        config.macd_slow_period,
        config.macd_signal_period,
    ) == (12, 26, 9)
    assert config.atr_period == 14
    assert config.atr_stop_multiple == 2
    assert config.initial_capital == 100000
    assert config.max_position_size == 1
    assert config.transaction_cost == 20
    assert config.slippage == 5
    assert config.force_liquidation is False
    assert V2_CONFIG.train_size == 250
    assert V2_CONFIG.test_size == 40
    assert V2_CONFIG.minimum_train_pnl == 0
    assert V2_CONFIG.minimum_train_trades == 5


def test_v2_signal_executes_at_next_open_without_future_data(monkeypatch):
    closes = [100 + index * 0.5 for index in range(55)]
    data = market_data(closes)
    config = create_v2_trading_config(V2_CONFIG).model_copy(
        update={"force_liquidation": True}
    )
    history_lengths = []

    original_builder = backtest_module.build_market_features

    def recording_builder(history, **kwargs):
        history_lengths.append(len(history))
        return original_builder(history, **kwargs)

    monkeypatch.setattr(backtest_module, "build_market_features", recording_builder)
    monkeypatch.setattr(
        backtest_module,
        "generate_trend_momentum_signal",
        lambda features: Signal(action=Action.BUY, confidence=1, reason="test"),
    )
    result = run_backtest(data, config, verbose=False)

    assert result.trades[0].entry_date == data[51].date
    assert history_lengths == [51, 52, 53, 54, 55]


def test_v2_gate_rejects_training_with_fewer_than_five_trades():
    flat = market_data([100.0] * 160)
    results, summary = evaluate_v2_system(
        [(flat[:120], flat[120:])], V2_CONFIG
    )
    assert results == []
    assert summary.accepted_windows == 0
    assert summary.rejected_windows == 1


def test_v2_diagnostics_explain_rejection_and_count_signals():
    flat = market_data([100.0] * 290)
    diagnostics = diagnose_v2_windows(
        [(flat[:250], flat[250:])], V2_CONFIG
    )
    diagnostic = diagnostics[0]
    assert diagnostic.accepted is False
    assert "train_pnl_not_positive" in diagnostic.rejection_reasons
    assert "fewer_than_five_completed_trades" in diagnostic.rejection_reasons
    assert diagnostic.hold_signals == 200
    assert diagnostic.entries == 0
    assert diagnostic.exits == 0
    assert diagnostic.atr_stop_signals == 0


def test_v2_atr_stop_is_close_based_and_executes_next_open(monkeypatch):
    closes = [100.0] * 55
    closes[52] = 80.0
    data = market_data(closes)
    config = create_v2_trading_config(V2_CONFIG)
    calls = 0

    def signal_once(features):
        nonlocal calls
        calls += 1
        action = Action.BUY if calls == 1 else Action.HOLD
        return Signal(action=action, confidence=1, reason="test")

    original_builder = backtest_module.build_market_features

    def fixed_atr_builder(history, **kwargs):
        return original_builder(history, **kwargs).model_copy(
            update={"atr": 10.0}
        )

    monkeypatch.setattr(backtest_module, "build_market_features", fixed_atr_builder)
    monkeypatch.setattr(
        backtest_module, "generate_trend_momentum_signal", signal_once
    )

    result = run_backtest(data, config, verbose=False)

    assert result.atr_stop_signals == 1
    assert result.trades[0].entry_date == data[51].date
    assert result.trades[0].exit_date == data[53].date
