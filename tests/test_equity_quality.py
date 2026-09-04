from datetime import datetime, timedelta

from trading_agent.core.market import MarketData
from trading_agent.data.quality import validate_equity_history


def row(day, open_=100, high=102, low=99, close=101, volume=1_000):
    return MarketData(
        date=datetime(2024, 1, 1) + timedelta(days=day), symbol="TEST",
        open=open_, high=high, low=low, close=close, volume=volume,
    )


def test_quality_report_rejects_duplicate_dates_and_invalid_ohlc():
    report = validate_equity_history([row(0), row(0, high=90)])
    assert not report.passed
    assert report.duplicate_dates == 1
    assert report.invalid_ohlc_rows == 1


def test_quality_report_flags_possible_unadjusted_corporate_action():
    report = validate_equity_history([row(0), row(1, open_=50, high=52, low=49, close=50)])
    assert report.passed
    assert report.large_return_jumps == 1
    assert report.issues[0].code == "corporate_action_candidate"

