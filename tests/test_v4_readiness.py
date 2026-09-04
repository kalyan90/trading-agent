from datetime import date, datetime, timedelta

from trading_agent.core.market import MarketData
from trading_agent.core.universe import UniverseMember
from trading_agent.execution.v4_readiness import check_v4_data_readiness


SIGNAL = date(2026, 9, 30)
AS_OF = date(2026, 10, 1)
INDEXES = ("NIFTY 50", "NIFTY NEXT 50", "NIFTY BANK")


def sessions(end, count):
    days = []
    day = end
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return list(reversed(days))


def history(symbol="A", include_open=True):
    rows = [MarketData(
        date=datetime.combine(day, datetime.min.time()), symbol=symbol,
        open=100 + index, high=101 + index, low=99 + index,
        close=100 + index, volume=200_000,
    ) for index, day in enumerate(sessions(SIGNAL, 253))]
    if include_open:
        rows.append(MarketData(
            date=datetime.combine(AS_OF, datetime.min.time()), symbol=symbol,
            open=400, high=401, low=399, close=400, volume=200_000,
        ))
    return rows


def members(snapshot=date(2026, 9, 4)):
    return [UniverseMember(
        as_of=snapshot, index_name=index_name, symbol="A",
    ) for index_name in INDEXES]


def test_ready_report_confirms_all_required_evidence():
    result = check_v4_data_readiness(
        {"A": history()}, history("NIFTY 50", include_open=False), members(),
        signal_date=SIGNAL, as_of=AS_OF,
    )
    assert result.ready
    assert result.active_symbols == 1
    assert result.history_ready_symbols == 1
    assert result.next_open_symbols == 1
    assert result.blockers == ()
    assert set(result.membership_dates) == set(INDEXES)


def test_missing_index_membership_history_and_next_open_are_blockers():
    result = check_v4_data_readiness(
        {}, [], members(date(2026, 10, 1)), signal_date=SIGNAL, as_of=SIGNAL,
    )
    assert not result.ready
    assert "as_of must be later than signal_date" in result.blockers
    assert "NIFTY 50 has no close on signal_date" in result.blockers
    assert "prospective active universe is empty" in result.blockers
    assert any("membership snapshot" in item for item in result.blockers)


def test_suspended_symbol_is_warning_when_other_symbol_can_trade():
    membership = []
    for index_name in INDEXES:
        membership.extend([
            UniverseMember(as_of=date(2026, 9, 4), index_name=index_name, symbol="A"),
            UniverseMember(as_of=date(2026, 9, 4), index_name=index_name, symbol="B"),
        ])
    result = check_v4_data_readiness(
        {"A": history("A"), "B": history("B", include_open=False)},
        history("NIFTY 50", include_open=False), membership,
        signal_date=SIGNAL, as_of=AS_OF,
    )
    assert result.ready
    assert result.history_ready_symbols == 2
    assert result.next_open_symbols == 1
    assert any("next-open evidence" in item for item in result.warnings)
