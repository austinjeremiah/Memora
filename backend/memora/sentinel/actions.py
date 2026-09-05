"""What Sentinel DOES when a finding will not go away.

Detecting a contradiction and reporting it is monitoring. An agent acts -- and
the action here is deliberately the one a clinician would take: when memory has
disagreed with itself across enough checks that it is clearly not a transient,
write that fact into the patient's own record so it travels with them.

THE TRIGGER EXISTS ONLY IN MEMORY. `runs_seen` comes from Sentinel's digest --
its own persisted memory of what it has already seen. Without that digest it
could never escalate, because it would not know it had seen this before. That
is the whole claim: persisted context changing what the agent does.

The action is idempotent. Escalating twice for the same finding would spam the
record it is trying to protect.
"""

import logging

from memora.ontology.events import (
    EVENT_COMPLICATION,
    SEVERITY_CRITICAL,
    ClinicalEvent,
)
from memora.sentinel.digest import Finding
from memora.sibyl.client import PatientMemory

log = logging.getLogger("memora.sentinel")

# Marks an event as written by Sentinel rather than ingested from a source
# record. A clinician reading the journal must be able to tell the difference.
SENTINEL_SOURCE_PREFIX = "sentinel-escalation"


def escalation_source_id(finding: Finding) -> str:
    """Stable per finding, so the same escalation is never written twice."""
    return f"{SENTINEL_SOURCE_PREFIX}:{finding.kind}:{finding.name}"


def already_escalated(memory: PatientMemory, finding: Finding) -> bool:
    source_id = escalation_source_id(finding)
    return any(
        (record.get("extra") or {}).get("source_id") == source_id
        for record in memory.read_history()
    )


def escalate(memory: PatientMemory, finding: Finding) -> str | None:
    """Write the escalation into the patient's journal. Returns the event id.

    Returns None if it was already written -- an agent that repeats itself is
    noise, and this record is the thing being protected.
    """
    if already_escalated(memory, finding):
        return None

    event = ClinicalEvent(
        event_type=EVENT_COMPLICATION,
        summary=(
            f"Flagged for review by Sentinel: {finding.kind}/{finding.name} "
            f"has conflicted with its own recorded history across "
            f"{finding.runs_seen} checks since {finding.first_seen_at[:10]}. "
            f"{finding.reason}"
        ),
        timestamp=finding.last_seen_at,
        related_kind=finding.kind,
        related_name=finding.name,
        source_id=escalation_source_id(finding),
        severity=SEVERITY_CRITICAL,
    )
    event_id = memory.log_event(event)
    log.info("sentinel escalated %s/%s for %s",
             finding.kind, finding.name, finding.patient_id)
    return event_id
