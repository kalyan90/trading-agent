"""Back-adjust raw NSE equity OHLCV for large ex-date reference discontinuities."""

import argparse
import csv
import json
from datetime import UTC, date, datetime
from pathlib import Path

from trading_agent.data.quality import DatasetManifest, file_sha256, write_manifest


FIELDS = ("date", "symbol", "series", "open", "high", "low", "close",
          "previous_close", "volume", "value", "trades", "isin")


def adjust_rows(rows, threshold):
    events = []
    factors = [1.0] * len(rows)
    cumulative = 1.0
    standard_factors = (0.1, 0.2, 0.25, 1 / 3, 0.4, 0.5, 2 / 3, 0.75,
                        0.8, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0)
    for index in range(len(rows) - 1, 0, -1):
        factors[index] = cumulative
        prior_close = float(rows[index - 1]["close"])
        reference = float(rows[index]["previous_close"])
        ratio = reference / prior_close if prior_close else 1.0
        method = "nse_ex_date_reference"
        if abs(ratio - 1) < threshold and prior_close:
            observed = float(rows[index]["close"]) / prior_close
            candidate = min(standard_factors, key=lambda value: abs(value - observed))
            if abs(observed - 1) >= threshold and abs(candidate - observed) <= 0.08:
                ratio = candidate
                method = "standard_factor_inferred_from_close_discontinuity"
        if abs(ratio - 1) >= threshold:
            events.append({
                "date": rows[index]["date"], "raw_prior_close": prior_close,
                "nse_ex_date_reference": reference, "back_adjustment_factor": ratio,
                "method": method,
            })
            cumulative *= ratio
    if rows:
        factors[0] = cumulative
    adjusted = []
    for row, factor in zip(rows, factors):
        item = dict(row)
        for field in ("open", "high", "low", "close", "previous_close"):
            item[field] = f"{float(row[field]) * factor:.6f}"
        item["volume"] = str(round(float(row["volume"]) / factor))
        adjusted.append(item)
    return adjusted, sorted(events, key=lambda item: item["date"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("data/stocks"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/stocks_adjusted"))
    parser.add_argument("--threshold", type=float, default=0.20)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for source_path in sorted(args.input_dir.glob("*_equity.csv")):
        with source_path.open(encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        adjusted, events = adjust_rows(rows, args.threshold)
        target = args.output_dir / source_path.name
        with target.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(adjusted)
        raw_manifest = DatasetManifest.model_validate_json(
            source_path.with_suffix(".manifest.json").read_text()
        )
        manifest = raw_manifest.model_copy(update={
            "downloaded_at": datetime.now(UTC).isoformat(),
            "adjustment_status": "back_adjusted_corporate_action_factors",
            "sha256": file_sha256(target),
        })
        write_manifest(target.with_suffix(".manifest.json"), manifest)
        target.with_suffix(".adjustments.json").write_text(
            json.dumps({
                "symbol": raw_manifest.symbol, "threshold": args.threshold,
                "method": "Back-adjust prior OHLC and inverse-adjust volume using "
                          "the NSE ex-date reference where available; otherwise snap "
                          "large-cap discontinuities to a documented standard split/bonus factor.",
                "events": events,
            }, indent=2) + "\n"
        )
        print(f"{raw_manifest.symbol}: {len(adjusted)} rows, {len(events)} adjustments")


if __name__ == "__main__":
    main()
