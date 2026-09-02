"""COLD journal event schema.

write_event is Sibyl's only append-only path. Its signature is keyword-only
(evaluated / acted / forward / extra / ts) and it rejects arbitrary keywords
with TypeError -- verified by execution against 0.7.0.

That means structured metadata does NOT need to be packed into a display
string, as an earlier draft assumed: `extra` accepts an arbitrary JSON object
and round-trips it intact, and `ts` carries the real clinical timestamp rather
than the wall-clock time of ingestion. The Evidence Resolver therefore reads
typed fields back out instead of parsing prose.
"""

from dataclasses import dataclass
from typing import Any

# event_type vocabulary
EVENT_MEDICATION_ADMINISTERED = "medication_administered"
EVENT_MEDICATION_DISCONTINUED = "medication_discontinued"
EVENT_ADVERSE_REACTION = "adverse_reaction"
EVENT_LAB_RESULT = "lab_result"
EVENT_PROCEDURE_PERFORMED = "procedure_performed"
EVENT_COMPLICATION = "complication"
EVENT_HANDOFF = "handoff"
EVENT_DIAGNOSIS_MADE = "diagnosis_made"

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"


@dataclass(frozen=True)
class ClinicalEvent:
    """One thing that HAPPENED, as opposed to what is currently TRUE."""

    event_type: str
    summary: str
    timestamp: str                      # ISO 8601, from the source record
    related_kind: str | None = None     # links back to a WARM entity category
    related_name: str | None = None     # links back to a WARM entity name
    source_id: str | None = None        # source record id, for provenance
    severity: str | None = None
    # Structured clinical detail from the source record: measured values with
    # units, codes, categories, dates. Prose in `summary` is for a human to
    # read; this is what downstream logic and trend-building actually use.
    details: dict[str, Any] | None = None

    def to_extra(self) -> dict[str, Any]:
        """The structured payload handed to write_event(extra=...)."""
        payload = {
            "event_type": self.event_type,
            "related_kind": self.related_kind,
            "related_name": self.related_name,
            "source_id": self.source_id,
            "severity": self.severity,
        }
        if self.details:
            payload["details"] = self.details
        return payload

    @staticmethod
    def from_record(record: dict[str, Any]) -> "ClinicalEvent":
        """Rebuild an event from a read_events() row."""
        extra = record.get("extra") or {}
        acted = record.get("acted") or []
        return ClinicalEvent(
            event_type=extra.get("event_type", ""),
            summary=acted[0] if acted else "",
            timestamp=record.get("ts", ""),
            related_kind=extra.get("related_kind"),
            related_name=extra.get("related_name"),
            source_id=extra.get("source_id"),
            severity=extra.get("severity"),
            details=extra.get("details"),
        )
