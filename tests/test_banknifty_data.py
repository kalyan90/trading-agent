from pathlib import Path

from trading_agent.data.index import load_index_history
from trading_agent.research.futures import build_front_month_series, load_futures_contracts


ROOT = Path(__file__).parents[1]


def test_banknifty_spot_history_is_complete_and_unique():
    rows = load_index_history(ROOT / "data/index", "NIFTY BANK")
    assert len(rows) == 1658
    assert rows[0].date.date().isoformat() == "2020-01-01"
    assert rows[-1].date.date().isoformat() == "2026-09-03"
    assert all(row.symbol == "NIFTY BANK" for row in rows)


def test_banknifty_futures_history_has_dated_lots_and_front_month():
    contracts = load_futures_contracts(ROOT / "data/futures", symbol="BANKNIFTY")
    assert 4900 < len(contracts) <= 4998
    assert {item.market_lot for item in contracts} >= {15, 20, 25, 30, 35}
    series = build_front_month_series(contracts)
    assert len({item.date.date() for item in series}) == len(series)
