from pathlib import Path

from trading_agent.data.universe import load_universe_snapshots


def test_official_nifty_100_snapshot_has_two_disjoint_fifty_stock_indexes():
    path = Path(__file__).parents[1] / "data/universe/nifty_100_constituents_2026-09-04.csv"
    members = load_universe_snapshots(path)
    by_index = {}
    for member in members:
        by_index.setdefault(member.index_name, set()).add(member.symbol)
    assert set(by_index) == {"NIFTY 50", "NIFTY NEXT 50"}
    assert len(by_index["NIFTY 50"]) == 50
    assert len(by_index["NIFTY NEXT 50"]) == 50
    assert by_index["NIFTY 50"].isdisjoint(by_index["NIFTY NEXT 50"])


def test_official_combined_snapshot_includes_banknifty_members():
    path = Path(__file__).parents[1] / "data/universe/nifty_100_bank_constituents_2026-09-04.csv"
    members = load_universe_snapshots(path)
    bank_symbols = {m.symbol for m in members if m.index_name == "NIFTY BANK"}
    assert len(bank_symbols) == 14
    assert len(members) == 114
