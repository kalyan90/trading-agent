from datetime import date

from trading_agent.data.nse import NseHistoricalClient


def client_without_network():
    return object.__new__(NseHistoricalClient)


def test_index_api_normalizes_and_deduplicates(monkeypatch):
    client = client_without_network()
    client.pause_seconds = 0
    raw = {"EOD_TIMESTAMP": "01-JAN-2026", "EOD_INDEX_NAME": "NIFTY 50",
           "EOD_OPEN_INDEX_VAL": 100, "EOD_HIGH_INDEX_VAL": 102,
           "EOD_LOW_INDEX_VAL": 99, "EOD_CLOSE_INDEX_VAL": 101,
           "HIT_TRADED_QTY": 10, "HIT_TURN_OVER": 20}
    monkeypatch.setattr(client, "_get", lambda *args: [raw, raw])

    rows = client.fetch_index_history(date(2026, 1, 1), date(2026, 1, 1))
    assert rows == [{"date": "01-JAN-2026", "index": "NIFTY 50",
                     "open": 100, "high": 102, "low": 99, "close": 101,
                     "traded_quantity": 10, "turnover_crores": 20}]


def test_futures_api_preserves_contract_identity(monkeypatch):
    client = client_without_network()
    client.pause_seconds = 0
    raw = {"FH_TIMESTAMP": "01-Jan-2026", "FH_EXPIRY_DT": "27-Jan-2026",
           "FH_INSTRUMENT": "FUTIDX", "FH_SYMBOL": "NIFTY",
           "FH_OPENING_PRICE": 100, "FH_MARKET_LOT": 65}
    monkeypatch.setattr(client, "_get", lambda *args: [raw])
    rows = client.fetch_futures_history(date(2026, 1, 1), date(2026, 1, 1))
    assert rows[0]["expiry"] == "27-Jan-2026"
    assert rows[0]["market_lot"] == 65


def test_api_rejects_reversed_date_range():
    client = client_without_network()
    client.pause_seconds = 0
    try:
        client.fetch_index_history(date(2026, 2, 1), date(2026, 1, 1))
    except ValueError as error:
        assert str(error) == "start must not be after end"
    else:
        raise AssertionError("Expected ValueError")
