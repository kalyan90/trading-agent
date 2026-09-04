"""Validate stored equity histories; optionally remove only byte-identical duplicates."""

import argparse
import csv
from datetime import date
from pathlib import Path

from trading_agent.data.equity import load_equity_csv
from trading_agent.data.quality import DatasetManifest, file_sha256, validate_equity_history, write_manifest


def remove_identical_duplicates(path: Path) -> int:
    with path.open(encoding="utf-8") as source:
        reader = csv.DictReader(source)
        fields = reader.fieldnames
        rows = list(reader)
    by_date = {}
    for row in rows:
        existing = by_date.get(row["date"])
        if existing is not None and existing != row:
            raise ValueError(f"{path}: conflicting rows for {row['date']}")
        by_date[row["date"]] = row
    unique = [by_date[day] for day in sorted(by_date)]
    removed = len(rows) - len(unique)
    if removed:
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            writer.writerows(unique)
        manifest_path = path.with_suffix(".manifest.json")
        manifest = DatasetManifest.model_validate_json(manifest_path.read_text())
        write_manifest(manifest_path, manifest.model_copy(update={
            "observations": len(unique),
            "first_date": date.fromisoformat(unique[0]["date"]),
            "last_date": date.fromisoformat(unique[-1]["date"]),
            "sha256": file_sha256(path),
        }))
    return removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/stocks"))
    parser.add_argument("--remove-identical-duplicates", action="store_true")
    args = parser.parse_args()
    for path in sorted(args.data_dir.glob("*_equity.csv")):
        removed = remove_identical_duplicates(path) if args.remove_identical_duplicates else 0
        rows = load_equity_csv(path)
        report = validate_equity_history(rows)
        manifest = DatasetManifest.model_validate_json(
            path.with_suffix(".manifest.json").read_text()
        )
        checksum_ok = manifest.sha256 == file_sha256(path)
        print(
            f"{report.symbol}: rows={report.observations} removed={removed} "
            f"quality={report.passed} checksum={checksum_ok} jumps={report.large_return_jumps}"
        )
        if not report.passed or not checksum_ok:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
