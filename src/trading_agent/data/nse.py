"""NSE historical index and derivatives client."""

import json
import time
from datetime import date, timedelta
from http.cookiejar import CookieJar
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


class NseHistoricalClient:
    base_url = "https://www.nseindia.com"
    index_report_url = f"{base_url}/reports-indices-historical-index-data"
    futures_report_url = f"{base_url}/report-detail/fo_eq_security"
    index_api_url = f"{base_url}/api/historicalOR/indicesHistory"
    futures_api_url = f"{base_url}/api/historicalOR/foCPV"
    equity_api_url = f"{base_url}/api/historical/securityArchives"
    equity_report_url = f"{base_url}/historical/price-and-volume-data-per-security"

    def __init__(self, timeout: int = 60, pause_seconds: float = 0.15):
        self.timeout = timeout
        self.pause_seconds = pause_seconds
        self.user_agent = "Mozilla/5.0 (compatible; trading-agent research client)"
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self._prime_session(self.index_report_url)

    def _prime_session(self, report_url):
        self.opener.open(
            Request(report_url, headers={"User-Agent": self.user_agent}),
            timeout=self.timeout,
        ).close()

    def _get(self, url, params, referer):
        request = Request(
            f"{url}?{urlencode(params)}",
            headers={"User-Agent": self.user_agent, "Referer": referer},
        )
        for attempt in range(3):
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    return json.load(response).get("data", [])
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    def _chunks(self, start: date, end: date):
        if start > end:
            raise ValueError("start must not be after end")
        current = start
        while current <= end:
            chunk_end = min(current + timedelta(days=26), end)
            yield current, chunk_end
            current = chunk_end + timedelta(days=1)

    def fetch_index_history(self, start: date, end: date, index="NIFTY 50"):
        records = {}
        for chunk_start, chunk_end in self._chunks(start, end):
            raw_rows = self._get(self.index_api_url, {
                "indexType": index,
                "from": chunk_start.strftime("%d-%m-%Y"),
                "to": chunk_end.strftime("%d-%m-%Y"),
            }, self.index_report_url)
            for raw in raw_rows:
                row = {
                    "date": raw.get("EOD_TIMESTAMP"),
                    "index": raw.get("EOD_INDEX_NAME"),
                    "open": raw.get("EOD_OPEN_INDEX_VAL"),
                    "high": raw.get("EOD_HIGH_INDEX_VAL"),
                    "low": raw.get("EOD_LOW_INDEX_VAL"),
                    "close": raw.get("EOD_CLOSE_INDEX_VAL"),
                    "traded_quantity": raw.get("HIT_TRADED_QTY"),
                    "turnover_crores": raw.get("HIT_TURN_OVER"),
                }
                records[(row["date"], row["index"])] = row
            time.sleep(self.pause_seconds)
        return list(records.values())

    def fetch_futures_history(
        self, start: date, end: date, symbol="NIFTY",
        instrument_type="FUTIDX",
    ):
        records = {}
        for chunk_start, chunk_end in self._chunks(start, end):
            raw_rows = self._get(self.futures_api_url, {
                "from": chunk_start.strftime("%d-%m-%Y"),
                "to": chunk_end.strftime("%d-%m-%Y"),
                "instrumentType": instrument_type,
                "symbol": symbol,
            }, self.futures_report_url)
            for raw in raw_rows:
                row = {
                    "date": raw.get("FH_TIMESTAMP"),
                    "expiry": raw.get("FH_EXPIRY_DT"),
                    "instrument": raw.get("FH_INSTRUMENT"),
                    "symbol": raw.get("FH_SYMBOL"),
                    "open": raw.get("FH_OPENING_PRICE"),
                    "high": raw.get("FH_TRADE_HIGH_PRICE"),
                    "low": raw.get("FH_TRADE_LOW_PRICE"),
                    "close": raw.get("FH_CLOSING_PRICE"),
                    "last_traded_price": raw.get("FH_LAST_TRADED_PRICE"),
                    "previous_close": raw.get("FH_PREV_CLS"),
                    "settlement_price": raw.get("FH_SETTLE_PRICE"),
                    "traded_quantity": raw.get("FH_TOT_TRADED_QTY"),
                    "traded_value_lakhs": raw.get("FH_TOT_TRADED_VAL"),
                    "open_interest": raw.get("FH_OPEN_INT"),
                    "change_in_open_interest": raw.get("FH_CHANGE_IN_OI"),
                    "market_lot": raw.get("FH_MARKET_LOT"),
                    "underlying_value": raw.get("FH_UNDERLYING_VALUE"),
                }
                key = (row["date"], row["expiry"], row["instrument"], row["symbol"])
                records[key] = row
            time.sleep(self.pause_seconds)
        return list(records.values())

    def fetch_equity_history(self, start: date, end: date, symbol: str,
                             series: str = "EQ"):
        records = {}
        for chunk_start, chunk_end in self._chunks(start, end):
            raw_rows = self._get(self.equity_api_url, {
                "from": chunk_start.strftime("%d-%m-%Y"),
                "to": chunk_end.strftime("%d-%m-%Y"),
                "symbol": symbol, "dataType": "priceVolumeDeliverable",
                "series": series,
            }, self.equity_report_url)
            for raw in raw_rows:
                row = {
                    "date": raw.get("CH_TIMESTAMP"),
                    "symbol": raw.get("CH_SYMBOL"),
                    "series": raw.get("CH_SERIES"),
                    "open": raw.get("CH_OPENING_PRICE"),
                    "high": raw.get("CH_TRADE_HIGH_PRICE"),
                    "low": raw.get("CH_TRADE_LOW_PRICE"),
                    "close": raw.get("CH_CLOSING_PRICE"),
                    "previous_close": raw.get("CH_PREVIOUS_CLS_PRICE"),
                    "volume": raw.get("CH_TOT_TRADED_QTY"),
                    "value": raw.get("CH_TOT_TRADED_VAL"),
                    "trades": raw.get("CH_TOTAL_TRADES"),
                    "isin": raw.get("CH_ISIN"),
                }
                records[(row["date"], row["symbol"], row["series"])] = row
            time.sleep(self.pause_seconds)
        return list(records.values())
