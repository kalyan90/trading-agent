"""Download official NSE NIFTY 50 index history by calendar year."""
import argparse
import csv
from datetime import date, datetime
from pathlib import Path
from trading_agent.data.nse import NseHistoricalClient

FIELDS = ("date", "index", "open", "high", "low", "close", "traded_quantity", "turnover_crores")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--output-dir", type=Path, default=Path("data/index"))
    args = parser.parse_args()
    if args.start_year > args.end_year:
        parser.error("start-year must not exceed end-year")
    client = NseHistoricalClient()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for year in range(args.start_year, args.end_year + 1):
        rows = client.fetch_index_history(date(year, 1, 1), min(date(year, 12, 31), date.today()))
        rows.sort(key=lambda row: datetime.strptime(row["date"], "%d-%b-%Y"))
        path = args.output_dir / f"nifty_50_index_{year}.csv"
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"{year}: {len(rows)} index rows -> {path}")

if __name__ == "__main__":
    main()
