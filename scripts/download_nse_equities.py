"""Download EQ-series histories for symbols in a universe snapshot."""

import argparse
import csv
import time
from datetime import UTC, date, datetime
from pathlib import Path

from trading_agent.data.nse import NseHistoricalClient
from trading_agent.data.universe import load_universe_snapshots
from trading_agent.data.equity import load_equity_csv
from trading_agent.data.quality import DatasetManifest, file_sha256, write_manifest


FIELDS = ("date", "symbol", "series", "open", "high", "low", "close",
          "previous_close", "volume", "value", "trades", "isin")
PILOT_SYMBOLS = (
    "BHARTIARTL", "HDFCBANK", "HINDUNILVR", "ICICIBANK", "INFY",
    "ITC", "LT", "RELIANCE", "SBIN", "TCS",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, default=Path("data/stocks"))
    parser.add_argument("--pause-symbols", type=float, default=1.0)
    parser.add_argument("--symbols", nargs="+", help="optional explicit symbol subset")
    parser.add_argument("--pilot", action="store_true", help="use the fixed 10-stock pilot")
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("start must not exceed end")
    universe_symbols = {member.symbol for member in load_universe_snapshots(args.universe)}
    requested = set(PILOT_SYMBOLS if args.pilot else (args.symbols or universe_symbols))
    unknown = requested - universe_symbols
    if unknown:
        parser.error(f"symbols not present in snapshot: {', '.join(sorted(unknown))}")
    symbols = sorted(requested)
    client = NseHistoricalClient(pause_seconds=0.2)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
        rows = client.fetch_equity_history(args.start, args.end, symbol)
        rows.sort(key=lambda row: datetime.strptime(row["date"], "%d-%b-%Y"))
        for row in rows:
            row["date"] = datetime.strptime(row["date"], "%d-%b-%Y").date().isoformat()
        path = args.output_dir / f"{symbol.lower()}_equity.csv"
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        loaded = load_equity_csv(path)
        manifest = DatasetManifest(
            symbol=symbol, source="National Stock Exchange of India",
            source_url=NseHistoricalClient.equity_api_url,
            downloaded_at=datetime.now(UTC).isoformat(), adjustment_status="raw_unadjusted",
            first_date=loaded[0].date.date() if loaded else None,
            last_date=loaded[-1].date.date() if loaded else None,
            observations=len(loaded), sha256=file_sha256(path),
        )
        write_manifest(path.with_suffix(".manifest.json"), manifest)
        print(f"{symbol}: {len(rows)} rows -> {path}")
        time.sleep(args.pause_symbols)


if __name__ == "__main__":
    main()
