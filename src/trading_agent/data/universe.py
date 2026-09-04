"""CSV persistence for point-in-time NSE index membership."""

import csv
from datetime import datetime
from pathlib import Path

from trading_agent.core.universe import UniverseMember


def load_universe_snapshots(path: Path) -> list[UniverseMember]:
    with path.open(encoding="utf-8") as source:
        return [
            UniverseMember(
                as_of=datetime.strptime(row["as_of"], "%Y-%m-%d").date(),
                index_name=row["index_name"], symbol=row["symbol"],
                company_name=row.get("company_name") or None,
                industry=row.get("industry") or None,
            )
            for row in csv.DictReader(source)
        ]
