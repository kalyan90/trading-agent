"""Standardized local cash-equity history loading."""

import csv
from datetime import datetime
from pathlib import Path

from trading_agent.core.market import MarketData


def load_equity_csv(path: Path) -> list[MarketData]:
    with path.open(encoding="utf-8") as source:
        rows = [MarketData(
            date=datetime.strptime(row["date"], "%Y-%m-%d"),
            symbol=row["symbol"], open=float(row["open"]),
            high=float(row["high"]), low=float(row["low"]),
            close=float(row["close"]), volume=int(float(row["volume"])),
        ) for row in csv.DictReader(source)]
    return sorted(rows, key=lambda item: item.date)


def load_equity_directory(path: Path):
    result = {}
    for csv_path in sorted(path.glob("*_equity.csv")):
        rows = load_equity_csv(csv_path)
        if rows:
            result[rows[0].symbol] = rows
    return result
