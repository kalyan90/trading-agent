from datetime import date

import pytest

from trading_agent.core.universe import (
    MembershipUnavailableError, UniverseMember, active_symbols,
)


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


def test_overlapping_members_are_deduplicated_across_indexes():
    members = [
        member(date(2024, 1, 1), "NIFTY 50", "BANK"),
        member(date(2024, 1, 1), "NIFTY BANK", "BANK"),
    ]
    assert active_symbols(members, date(2024, 2, 1)) == {"BANK"}


def test_missing_snapshot_can_fail_explicitly():
    with pytest.raises(MembershipUnavailableError):
        active_symbols([], date(2024, 1, 1), require_snapshot=True)


def test_future_snapshot_is_never_visible():
    members = [member(date(2025, 1, 1), "NIFTY 50", "FUTURE")]
    assert active_symbols(members, date(2024, 12, 31)) == set()
