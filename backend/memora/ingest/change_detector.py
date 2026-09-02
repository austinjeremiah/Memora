"""New / confirmed / changed detection for WARM facts.

Sibyl entities overwrite in place -- UNIQUE (tenant_id, category, name), no
versioning. This module is what preserves history on top of that: before a fact
is overwritten, the transition is written to the append-only journal, so the
WARM row can say what is true now while the journal still says how it got there.

The comparison is the subtle part. get_fact returns the entity ROW, not the
clinical payload, so comparing it directly against a proposed body is always
unequal -- every ingest would look like a change, log a spurious transition
event, and rewrite the row. Payload and status are compared separately, against
the right fields.
"""

from dataclasses import dataclass
from enum import Enum

from memora.ontology.events import ClinicalEvent
from memora.sibyl.client import PatientMemory

# Fields that change on every observation and therefore never constitute a
# clinical change on their own.
_VOLATILE_FIELDS = frozenset({"last_seen"})


class ChangeType(str, Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    CHANGED = "changed"


@dataclass(frozen=True)
class ChangeResult:
    change: ChangeType
    kind: str
    name: str
    previous_status: str | None = None
    new_status: str | None = None
    # The body as it was before this write. Carried so Sentinel can judge the
    # delta without re-reading Sibyl to re-derive what this function already
    # knew -- that would be duplicated work and a second place the "what
    # changed" logic could drift out of step with this one.
    previous_body: dict | None = None


def apply_fact_change(memory: PatientMemory, kind: str, name: str,
                      new_body: dict, event: ClinicalEvent,
                      status: str | None = None) -> ChangeResult:
    """Write a fact, journalling the transition when it is a real change."""
    existing = memory.get_fact(kind, name)

    if existing is None:
        memory.set_fact(kind, name, new_body, status=status)
        memory.log_event(event)
        return ChangeResult(ChangeType.NEW, kind, name, None, status, None)

    # Compare MATERIAL fields only, against the right parts of the row: the
    # payload against body, the lifecycle marker against the status column.
    #
    # "Material" excludes last_seen. A fact re-observed at a new time has not
    # changed -- it has been confirmed. Treating a refreshed timestamp as a
    # change made 318 of 400 ingested events log a spurious transition and
    # rewrite the row, which is both wrong and expensive against a 5 MB cap.
    old = existing["body"] if isinstance(existing["body"], dict) else {}
    material_old = {k: v for k, v in old.items() if k not in _VOLATILE_FIELDS}
    material_new = {k: v for k, v in new_body.items() if k not in _VOLATILE_FIELDS}

    if material_old == material_new and existing["status"] == status:
        # Refresh the row so last_seen stays current, but journal nothing:
        # the caller logs the observation itself.
        memory.set_fact(kind, name, new_body, status=status)
        return ChangeResult(ChangeType.CONFIRMED, kind, name,
                            existing["status"], status, old)

    previous_status = existing["status"]
    transition = ClinicalEvent(
        event_type=event.event_type,
        summary=(f"{event.summary} [status {previous_status or 'none'} "
                 f"-> {status or 'none'}]"),
        timestamp=event.timestamp,
        related_kind=kind,
        related_name=name,
        source_id=event.source_id,
        severity=event.severity,
    )
    # Journal BEFORE the overwrite: the WARM row is about to lose the old
    # value, so the history has to exist first.
    memory.log_event(transition)
    memory.set_fact(kind, name, new_body, status=status)
    return ChangeResult(ChangeType.CHANGED, kind, name, previous_status, status, old)
