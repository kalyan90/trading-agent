"""Build raw equity histories for declared NSE index snapshots from bhavcopies."""

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from trading_agent.data.nse import NseBhavcopyClient
from trading_agent.data.quality import DatasetManifest, file_sha256, write_manifest
from trading_agent.data.universe import load_universe_snapshots

from download_nse_equities import PILOT_SYMBOLS


FIELDS = ("date", "symbol", "series", "open", "high", "low", "close",
          "previous_close", "volume", "value", "trades", "isin")


def weekdays(start, end):
    current = start
    while current <= end:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


def normalize(raw):
    return {
        "date": datetime.strptime(raw["DATE1"], "%d-%b-%Y").date().isoformat(),
        "symbol": raw["SYMBOL"], "series": raw["SERIES"],
        "open": raw["OPEN_PRICE"], "high": raw["HIGH_PRICE"],
        "low": raw["LOW_PRICE"], "close": raw["CLOSE_PRICE"],
        "previous_close": raw["PREV_CLOSE"], "volume": raw["TTL_TRD_QNTY"],
        "value": raw["TURNOVER_LACS"], "trades": raw["NO_OF_TRADES"],
        "isin": "",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, default=Path("data/stocks"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument(
        "--indexes", nargs="+",
        choices=("NIFTY 50", "NIFTY NEXT 50", "NIFTY BANK"),
        help="select snapshot groups; defaults to their deduplicated union",
    )
    args = parser.parse_args()
    members = load_universe_snapshots(args.universe)
    universe = {
        member.symbol for member in members
        if not args.indexes or member.index_name in set(args.indexes)
    }
    selected = set(PILOT_SYMBOLS if args.pilot else (args.symbols or universe))
    unknown = selected - universe
    if unknown:
        parser.error(f"symbols not present in snapshot: {', '.join(sorted(unknown))}")
    sessions = list(weekdays(args.start, args.end))
    histories = {symbol: [] for symbol in selected}
    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(NseBhavcopyClient().fetch_day, session): session
            for session in sessions
        }
        for future in as_completed(futures):
            session = futures[future]
            try:
                raw_rows = future.result()
            except Exception as error:
                print(f"warning: {session} skipped after retries: {error}")
                raw_rows = []
            for raw in raw_rows:
                # Some holiday URLs return a neighbouring session instead of 404.
                # Never accept a payload whose exchange date differs from the request.
                if "DATE1" not in raw:
                    continue
                exchange_day = datetime.strptime(raw["DATE1"], "%d-%b-%Y").date()
                if (exchange_day == session and raw.get("SERIES") == "EQ"
                        and raw.get("SYMBOL") in selected):
                    histories[raw["SYMBOL"]].append(normalize(raw))
            completed += 1
            if completed % 250 == 0:
                print(f"processed {completed}/{len(sessions)} weekdays")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    downloaded_at = datetime.now(UTC).isoformat()
    for symbol, rows in sorted(histories.items()):
        rows.sort(key=lambda row: row["date"])
        path = args.output_dir / f"{symbol.lower()}_equity.csv"
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        write_manifest(path.with_suffix(".manifest.json"), DatasetManifest(
            symbol=symbol, source="NSE official security bhavcopy archive",
            source_url=NseBhavcopyClient.url_template,
            downloaded_at=downloaded_at, adjustment_status="raw_unadjusted",
            first_date=date.fromisoformat(rows[0]["date"]) if rows else None,
            last_date=date.fromisoformat(rows[-1]["date"]) if rows else None,
            observations=len(rows), sha256=file_sha256(path),
        ))
        print(f"{symbol}: {len(rows)} rows -> {path}")


if __name__ == "__main__":
    main()
