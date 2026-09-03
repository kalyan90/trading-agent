from datetime import date

import pytest

from trading_agent.core.instrument import NIFTY_FUTURES_2026


def test_current_nifty_futures_contract_snapshot():
    contract = NIFTY_FUTURES_2026
    assert contract.exchange_symbol == "NIFTY"
    assert contract.lot_size == 65
    assert contract.point_value == 65
    assert contract.effective_from == date(2026, 1, 27)
    assert contract.source_reference == "NSE/FAOP/70616"


def test_contract_converts_points_and_notional_to_money():
    assert NIFTY_FUTURES_2026.monetary_pnl(10, lots=2) == 1300
    assert NIFTY_FUTURES_2026.notional_value(25000) == 1625000


def test_contract_rejects_invalid_lots_and_price():
    with pytest.raises(ValueError):
        NIFTY_FUTURES_2026.monetary_pnl(10, lots=0)
    with pytest.raises(ValueError):
        NIFTY_FUTURES_2026.notional_value(0)
