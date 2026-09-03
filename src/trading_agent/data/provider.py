"""Local spot-market data loading."""

from datetime import datetime
from trading_agent.core.market import MarketData
import csv
from pathlib import Path


def get_market_data() -> MarketData:
    return MarketData(
        symbol="NIFTY",
        open=24900,
        high=25100,
        low=24850,
        close=25050,
        volume=100000
    )

def load_market_data_from_csv(file_path: str) -> list[MarketData]:
    market_data = []

    with open(file_path, "r") as file:
        reader = csv.DictReader(file)

        for row in reader:
            market_data.append(
                MarketData(
                    date=datetime.strptime(row["Date"], "%d %b %Y"),
                    symbol="NIFTY 50",
                    open=row["Open"],
                    high=row["High"],
                    low=row["Low"],
                    close=row["Close"],
                    volume=None,
                )
            )

    return market_data

def get_historical_market_data() -> list[MarketData]:
    data_folder = Path("data")
    files = data_folder.glob("*.csv")

    market_data = []

    for file_path in files:
        data = load_market_data_from_csv(file_path)
        market_data.extend(data)

    market_data.sort(key=lambda market: market.date)

    return market_data
