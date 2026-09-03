"""Legacy CSV streaming helper."""

import csv
from trading_agent.core.market import MarketData
from trading_agent.signals.strategy import generate_signal

with open("data/nifty.csv", "r") as file:
    reader = csv.DictReader(file)

    for row in reader:
        market = MarketData(
            symbol=row["symbol"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"]
        )

        print(market)
        change = market.price_change()
        signal = generate_signal(change)

        print(
            market.symbol,
            market.close,
            change,
            signal.action
        )   
