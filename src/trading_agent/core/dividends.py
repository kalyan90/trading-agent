"""Optional authoritative cash-dividend interface for total-return research."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class DividendEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    ex_date: date
    cash_per_share: float = Field(gt=0)
    source: str
    source_url: str
    verified: bool = True


def dividends_by_symbol_date(events: list[DividendEvent] | None):
    result = {}
    for event in events or []:
        if not event.verified or not event.source_url:
            raise ValueError("dividend events must carry an authoritative source URL")
        key = (event.symbol, event.ex_date)
        if key in result:
            raise ValueError(f"duplicate dividend event: {key}")
        result[key] = event.cash_per_share
    return result
