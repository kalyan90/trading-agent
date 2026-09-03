import csv
from datetime import datetime
from pathlib import Path


DATA_DIR = Path(__file__).parents[1] / "data" / "futures"
EXPECTED_MINIMUM_DAYS = {
    2020: 240, 2021: 240, 2022: 240, 2023: 240,
    2024: 240, 2025: 240, 2026: 160,
}


def test_yearly_nifty_futures_dumps_are_complete_and_unique():
    for year, minimum_days in EXPECTED_MINIMUM_DAYS.items():
        path = DATA_DIR / f"nifty_futures_contracts_{year}.csv"
        with path.open(encoding="utf-8") as source:
            rows = list(csv.DictReader(source))

        keys = {
            (row["date"], row["expiry"], row["instrument"], row["symbol"])
            for row in rows
        }
        dates = {
            datetime.strptime(row["date"], "%d-%b-%Y").date()
            for row in rows
        }

        assert len(keys) == len(rows)
        assert len(dates) >= minimum_days
        assert all(row["instrument"] == "FUTIDX" for row in rows)
        assert all(row["symbol"] == "NIFTY" for row in rows)
        assert all(datetime.strptime(row["date"], "%d-%b-%Y").year == year for row in rows)


def test_download_preserves_historical_market_lot_values():
    lots = set()
    for path in DATA_DIR.glob("nifty_futures_contracts_*.csv"):
        with path.open(encoding="utf-8") as source:
            lots.update(
                int(float(row["market_lot"]))
                for row in csv.DictReader(source)
                if row["market_lot"]
            )

    assert {25, 50, 65, 75}.issubset(lots)
