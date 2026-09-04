"""Deterministic quality checks and provenance for cash-equity histories."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from trading_agent.core.market import MarketData


class DataQualityIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: str
    code: str
    message: str


class EquityDataQualityReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    observations: int
    first_date: date | None
    last_date: date | None
    duplicate_dates: int = 0
    non_monotonic_dates: int = 0
    invalid_ohlc_rows: int = 0
    non_positive_prices: int = 0
    non_positive_volume_rows: int = 0
    large_return_jumps: int = 0
    issues: tuple[DataQualityIssue, ...] = ()

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


class DatasetManifest(BaseModel):
    """Sidecar metadata; adjustment claims must be explicit and auditable."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    source: str
    source_url: str
    downloaded_at: str
    series: str = "EQ"
    adjustment_status: str = "raw_unadjusted"
    first_date: date | None
    last_date: date | None
    observations: int = Field(ge=0)
    sha256: str


def validate_equity_history(
    rows: list[MarketData], *, jump_threshold: float = 0.35,
) -> EquityDataQualityReport:
    symbol = rows[0].symbol if rows else "UNKNOWN"
    dates = [row.date.date() for row in rows]
    duplicate_dates = len(dates) - len(set(dates))
    non_monotonic = sum(right <= left for left, right in zip(dates, dates[1:]))
    invalid_ohlc = sum(
        row.high < max(row.open, row.close)
        or row.low > min(row.open, row.close)
        or row.high < row.low
        for row in rows
    )
    non_positive_prices = sum(
        min(row.open, row.high, row.low, row.close) <= 0 for row in rows
    )
    non_positive_volume = sum(row.volume <= 0 for row in rows)
    jumps = sum(
        abs(current.close / previous.close - 1) >= jump_threshold
        for previous, current in zip(rows, rows[1:])
        if previous.close > 0
    )
    issues = []
    for count, code, message in (
        (duplicate_dates, "duplicate_dates", "duplicate trading dates"),
        (non_monotonic, "non_monotonic_dates", "dates are not strictly increasing"),
        (invalid_ohlc, "invalid_ohlc", "OHLC bounds are inconsistent"),
        (non_positive_prices, "non_positive_price", "prices must be positive"),
    ):
        if count:
            issues.append(DataQualityIssue(
                severity="error", code=code, message=f"{count} {message}",
            ))
    if non_positive_volume:
        issues.append(DataQualityIssue(
            severity="warning", code="non_positive_volume",
            message=f"{non_positive_volume} rows have non-positive volume",
        ))
    if jumps:
        issues.append(DataQualityIssue(
            severity="warning", code="corporate_action_candidate",
            message=(f"{jumps} close-to-close moves exceed {jump_threshold:.0%}; "
                     "verify splits, bonuses, or bad ticks"),
        ))
    return EquityDataQualityReport(
        symbol=symbol, observations=len(rows),
        first_date=dates[0] if dates else None,
        last_date=dates[-1] if dates else None,
        duplicate_dates=duplicate_dates, non_monotonic_dates=non_monotonic,
        invalid_ohlc_rows=invalid_ohlc, non_positive_prices=non_positive_prices,
        non_positive_volume_rows=non_positive_volume, large_return_jumps=jumps,
        issues=tuple(issues),
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(path: Path, manifest: DatasetManifest) -> None:
    path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n")

