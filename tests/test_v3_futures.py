from datetime import datetime
from pathlib import Path
import pytest

from trading_agent.research.futures import (
    FuturesMarketData,
    atr_stop_triggered,
    build_front_month_series,
    evaluate_futures_execution,
    load_futures_contracts,
)
from trading_agent.core.config import V1_CONFIG, V2_CONFIG
from trading_agent.data.provider import get_historical_market_data
from trading_agent.research.experiment import split_development_and_holdout
from trading_agent.execution.futures_account import (
    FuturesAccount, FuturesChargeConfig, FuturesMarginConfig,
)


def contract(day, expiry, price=100, lot=65):
    return FuturesMarketData(
        date=datetime.fromisoformat(day), expiry=datetime.fromisoformat(expiry),
        symbol="NIFTY", open=price, high=price + 1, low=price - 1,
        close=price, settlement_price=price, volume=1, open_interest=1,
        market_lot=lot,
    )


def test_front_month_selection_rolls_after_expiry_session():
    records = [
        contract("2026-01-26", "2026-01-27"),
        contract("2026-01-26", "2026-02-24"),
        contract("2026-01-27", "2026-01-27"),
        contract("2026-01-27", "2026-02-24"),
        contract("2026-01-28", "2026-02-24"),
    ]
    series = build_front_month_series(records)
    assert [item.expiry.day for item in series] == [27, 27, 24]


def test_futures_atr_stop_uses_supplied_config_multiple():
    assert atr_stop_triggered(80, entry_price=100, entry_atr=10, stop_multiple=2)
    assert not atr_stop_triggered(80, entry_price=100, entry_atr=10, stop_multiple=3)


def test_real_futures_loader_resolves_blank_lots():
    root = Path(__file__).parents[1]
    records = load_futures_contracts(root / "data" / "futures")
    assert 4900 < len(records) <= 4994
    assert all(record.market_lot > 0 for record in records)


def test_front_month_series_has_one_contract_per_session():
    root = Path(__file__).parents[1]
    contracts = load_futures_contracts(root / "data" / "futures")
    series = build_front_month_series(contracts)
    dates = [record.date.date() for record in series]
    assert dates == sorted(set(dates))
    assert all(record.date.date() <= record.expiry.date() for record in series)


def test_loader_requires_symbol_when_directory_contains_multiple_instruments(tmp_path):
    header = "symbol,expiry\n"
    (tmp_path / "nifty_futures_contracts_2026.csv").write_text(
        header + "NIFTY,27-Jan-2026\n", encoding="utf-8"
    )
    (tmp_path / "reliance_futures_contracts_2026.csv").write_text(
        header + "RELIANCE,27-Jan-2026\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="pass symbol explicitly"):
        load_futures_contracts(tmp_path)


def test_real_futures_development_result_is_reproducible():
    root = Path(__file__).parents[1]
    contracts = load_futures_contracts(root / "data" / "futures")
    futures = build_front_month_series(contracts)
    spot, _ = split_development_and_holdout(
        get_historical_market_data(), V1_CONFIG.final_holdout_size
    )
    result = evaluate_futures_execution(spot, futures, V2_CONFIG)
    assert result.accepted_windows == 6
    assert result.rejected_windows == 22
    assert result.strategy_trades == 8
    assert result.gate_liquidations == 1
    assert result.rolls == 3
    assert result.total_pnl == pytest.approx(49_260.0)
    assert result.max_drawdown == pytest.approx(57_857.5)
    assert result.missing_futures_dates == 5


def test_futures_account_daily_settlement_and_margin_call():
    account = FuturesAccount(
        initial_cash=1_000, transaction_cost=20,
        margin=FuturesMarginConfig(
            initial_margin_rate=0.10, maintenance_margin_rate=0.08
        ),
    )
    assert account.open(price=100, lot=50)
    assert account.cash == 990
    assert not account.settle(95)
    assert account.cash == 740
    assert account.settle(85)
    assert account.cash == 240
    account.close(84)
    assert account.cash == 180


def test_maintenance_margin_cannot_exceed_initial_margin():
    with pytest.raises(ValueError, match="maintenance margin"):
        FuturesMarginConfig(
            initial_margin_rate=0.10, maintenance_margin_rate=0.11
        )


def test_dated_futures_stt_rates_and_one_sided_stamp_duty():
    charges = FuturesChargeConfig(
        brokerage_per_order=0, exchange_transaction_rate=0,
        sebi_turnover_rate=0, stamp_duty_buy_rate=0.00002, gst_rate=0,
    )
    assert charges.order_charge(datetime(2022, 1, 1).date(), 100, 100, True) == 0.2
    assert charges.order_charge(datetime(2022, 1, 1).date(), 100, 100, False) == 1.0
    assert charges.order_charge(datetime(2023, 4, 1).date(), 100, 100, False) == 1.25
    assert charges.order_charge(datetime(2024, 10, 1).date(), 100, 100, False) == 2.0


def test_real_futures_margin_proxy_rejects_unfunded_entries_at_one_lakh():
    root = Path(__file__).parents[1]
    futures = build_front_month_series(
        load_futures_contracts(root / "data" / "futures")
    )
    spot, _ = split_development_and_holdout(
        get_historical_market_data(), V1_CONFIG.final_holdout_size
    )
    result = evaluate_futures_execution(
        spot, futures, V2_CONFIG, FuturesMarginConfig()
    )
    assert result.rejected_entries == 40
    assert result.strategy_trades == 0
    assert result.total_pnl == 0
    assert result.benchmark_entry_rejected


def test_ten_lakh_futures_result_with_margin_and_dated_charges():
    root = Path(__file__).parents[1]
    futures = build_front_month_series(
        load_futures_contracts(root / "data" / "futures")
    )
    spot, _ = split_development_and_holdout(
        get_historical_market_data(), V1_CONFIG.final_holdout_size
    )
    result = evaluate_futures_execution(
        spot, futures, V2_CONFIG, FuturesMarginConfig(),
        initial_capital=1_000_000, charge_config=FuturesChargeConfig(),
    )
    assert result.rejected_entries == 0
    assert result.margin_calls == 0
    assert result.strategy_trades == 8
    assert result.total_pnl == pytest.approx(46_860.86545475)
    assert result.total_charges == pytest.approx(2_619.13454525)
    assert result.peak_margin == pytest.approx(178_638.75)
    assert result.benchmark_pnl == pytest.approx(341_304.7799152)
