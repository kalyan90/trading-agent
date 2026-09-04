"""Point-in-time research universe definitions."""

from datetime import date

from pydantic import BaseModel, ConfigDict, model_validator


class MembershipUnavailableError(ValueError):
    """No snapshot was knowable on the requested evaluation date."""


class UniverseMember(BaseModel):
    model_config = ConfigDict(frozen=True)

    as_of: date
    index_name: str
    symbol: str
    company_name: str | None = None
    industry: str | None = None
    record_type: str = "snapshot"
    effective_from: date | None = None
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_interval(self):
        if self.record_type not in {"snapshot", "interval"}:
            raise ValueError("record_type must be snapshot or interval")
        if self.record_type == "interval" and self.effective_from is None:
            raise ValueError("interval membership requires effective_from")
        if (self.effective_from is not None and self.effective_to is not None
                and self.effective_to < self.effective_from):
            raise ValueError("effective_to precedes effective_from")
        return self


def active_symbols(
    members: list[UniverseMember], as_of: date, indexes: set[str] | None = None,
    *, require_snapshot: bool = False,
) -> set[str]:
    """Select only the latest snapshot available on or before the research date."""
    eligible = [m for m in members if m.as_of <= as_of]
    if indexes:
        eligible = [m for m in eligible if m.index_name in indexes]
    intervals = [m for m in eligible if m.record_type == "interval"]
    snapshots = [m for m in eligible if m.record_type == "snapshot"]
    interval_symbols = {
        member.symbol for member in intervals
        if member.effective_from <= as_of
        and (member.effective_to is None or as_of <= member.effective_to)
    }
    if not snapshots and not interval_symbols:
        if require_snapshot:
            raise MembershipUnavailableError(
                f"no universe snapshot known on or before {as_of.isoformat()}"
            )
        return set()
    latest_by_index = {}
    for member in snapshots:
        latest_by_index[member.index_name] = max(
            member.as_of, latest_by_index.get(member.index_name, member.as_of)
        )
    return {
        member.symbol for member in snapshots
        if member.as_of == latest_by_index[member.index_name]
    } | interval_symbols


def membership_status(members: list[UniverseMember], start: date, end: date) -> str:
    """Classify whether snapshots support honest point-in-time claims."""
    if not members:
        return "unavailable"
    snapshots = sorted({member.as_of for member in members})
    if snapshots[0] > start:
        return "retrospective_current_snapshot"
    if snapshots[-1] > end:
        return "point_in_time"  # future snapshots are ignored by active_symbols
    return "point_in_time"
