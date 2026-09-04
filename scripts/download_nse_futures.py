"""Download official NSE index or stock futures history by calendar year."""
import argparse
import csv
from datetime import date, datetime
from pathlib import Path
from trading_agent.data.nse import NseHistoricalClient

FIELDS = ("date", "expiry", "instrument", "symbol", "open", "high", "low", "close", "last_traded_price", "previous_close", "settlement_price", "traded_quantity", "traded_value_lakhs", "open_interest", "change_in_open_interest", "market_lot", "underlying_value")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--output-dir", type=Path, default=Path("data/futures"))
    parser.add_argument("--symbol", default="NIFTY")
    parser.add_argument(
        "--instrument-type", choices=("FUTIDX", "FUTSTK"), default="FUTIDX"
    )
    args = parser.parse_args()
    if args.start_year > args.end_year:
        parser.error("start-year must not exceed end-year")
    client = NseHistoricalClient()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for year in range(args.start_year, args.end_year + 1):
        rows = client.fetch_futures_history(
            date(year, 1, 1), min(date(year, 12, 31), date.today()),
            symbol=args.symbol, instrument_type=args.instrument_type,
        )
        rows.sort(key=lambda row: (datetime.strptime(row["date"], "%d-%b-%Y"), datetime.strptime(row["expiry"], "%d-%b-%Y")))
        slug = args.symbol.lower().replace(" ", "_").replace("&", "and")
        path = args.output_dir / f"{slug}_futures_contracts_{year}.csv"
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"{year}: {len(rows)} contract-day rows -> {path}")

if __name__ == "__main__":
    main()
