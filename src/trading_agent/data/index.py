"""Load normalized yearly index histories downloaded from NSE."""

import csv
from datetime import datetime
from pathlib import Path

from trading_agent.core.market import MarketData


def load_index_history(data_dir: Path, index_name: str):
    slug = index_name.lower().replace(" ", "_").replace("&", "and")
    records = []
    for path in sorted(data_dir.glob(f"{slug}_index_*.csv")):
        with path.open(encoding="utf-8") as source:
            for row in csv.DictReader(source):
                records.append(MarketData(
                    date=datetime.strptime(row["date"], "%d-%b-%Y"),
                    symbol=row["index"], open=float(row["open"]),
                    high=float(row["high"]), low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(float(row["traded_quantity"]))
                    if row["traded_quantity"] else None,
                ))
    unique = {record.date.date(): record for record in records}
    return [unique[day] for day in sorted(unique)]


def load_nifty50_price_history(data_dir: Path) -> list[MarketData]:
    """Load the stored official NSE NIFTY 50 price-return CSV series."""
    records = []
    for path in sorted(data_dir.glob("NIFTY 50_Historical_PR_*.csv")):
        with path.open(encoding="utf-8-sig") as source:
            for row in csv.DictReader(source):
                records.append(MarketData(
                    date=datetime.strptime(row["Date"], "%d %b %Y"),
                    symbol=row["Index Name"], open=float(row["Open"]),
                    high=float(row["High"]), low=float(row["Low"]),
                    close=float(row["Close"]), volume=None,
                ))
    unique = {record.date.date(): record for record in records}
    return [unique[day] for day in sorted(unique)]
