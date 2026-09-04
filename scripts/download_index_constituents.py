"""Persist dated snapshots of official Nifty index constituent CSV files."""

import argparse
import csv
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen


INDEX_FILES = {
    "NIFTY 50": "ind_nifty50list.csv",
    "NIFTY NEXT 50": "ind_niftynext50list.csv",
    "NIFTY BANK": "ind_niftybanklist.csv",
}
FIELDS = ("as_of", "index_name", "symbol", "company_name", "industry", "series", "isin")


def download(index_name: str, as_of: date):
    filename = INDEX_FILES[index_name]
    url = f"https://www.niftyindices.com/IndexConstituent/{filename}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        text = response.read().decode("utf-8-sig")
    return [{
        "as_of": as_of.isoformat(), "index_name": index_name,
        "symbol": row["Symbol"], "company_name": row["Company Name"],
        "industry": row["Industry"], "series": row["Series"],
        "isin": row["ISIN Code"],
    } for row in csv.DictReader(text.splitlines())]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, default=Path("data/universe"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for index_name in INDEX_FILES:
        rows.extend(download(index_name, args.as_of))
    path = args.output_dir / f"nifty_100_bank_constituents_{args.as_of.isoformat()}.csv"
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} membership rows -> {path}")


if __name__ == "__main__":
    main()
