"""Download EQ-series histories for symbols in a universe snapshot."""

import argparse
import csv
import time
from datetime import date, datetime
from pathlib import Path

from trading_agent.data.nse import NseHistoricalClient
from trading_agent.data.universe import load_universe_snapshots


FIELDS = ("date", "symbol", "series", "open", "high", "low", "close",
          "previous_close", "volume", "value", "trades", "isin")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, default=Path("data/stocks"))
    parser.add_argument("--pause-symbols", type=float, default=1.0)
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("start must not exceed end")
    symbols = sorted({member.symbol for member in load_universe_snapshots(args.universe)})
    client = NseHistoricalClient(pause_seconds=0.2)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
        rows = client.fetch_equity_history(args.start, args.end, symbol)
        rows.sort(key=lambda row: datetime.fromisoformat(row["date"]))
        path = args.output_dir / f"{symbol.lower()}_equity.csv"
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"{symbol}: {len(rows)} rows -> {path}")
        time.sleep(args.pause_symbols)


if __name__ == "__main__":
    main()
