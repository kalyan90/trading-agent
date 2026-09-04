from datetime import date

from trading_agent.core.universe import UniverseMember, active_symbols


def member(day, index, symbol):
    return UniverseMember(as_of=day, index_name=index, symbol=symbol)


def test_universe_uses_latest_snapshot_without_survivorship_lookahead():
    members = [
        member(date(2024, 1, 1), "NIFTY 50", "OLD"),
        member(date(2025, 1, 1), "NIFTY 50", "NEW"),
        member(date(2024, 1, 1), "NIFTY NEXT 50", "NEXT"),
    ]
    assert active_symbols(members, date(2024, 6, 1), {"NIFTY 50"}) == {"OLD"}
    assert active_symbols(members, date(2025, 6, 1), {"NIFTY 50"}) == {"NEW"}
    assert active_symbols(members, date(2023, 1, 1)) == set()
