"""Standardized local cash-equity history loading."""

import csv
from datetime import datetime
from pathlib import Path

from trading_agent.core.market import MarketData
from trading_agent.data.quality import validate_equity_history


def load_equity_csv(path: Path, *, require_quality: bool = True) -> list[MarketData]:
    with path.open(encoding="utf-8") as source:
        rows = [MarketData(
            date=datetime.strptime(row["date"], "%Y-%m-%d"),
            symbol=row["symbol"], open=float(row["open"]),
            high=float(row["high"]), low=float(row["low"]),
            close=float(row["close"]), volume=int(float(row["volume"])),
        ) for row in csv.DictReader(source)]
    rows = sorted(rows, key=lambda item: item.date)
    report = validate_equity_history(rows)
    if require_quality and not report.passed:
        errors = "; ".join(issue.message for issue in report.issues
                           if issue.severity == "error")
        raise ValueError(f"{path}: equity data quality failed: {errors}")
    return rows


def load_equity_directory(path: Path):
    result = {}
    for csv_path in sorted(path.glob("*_equity.csv")):
        rows = load_equity_csv(csv_path)
        if rows:
            result[rows[0].symbol] = rows
    return result
