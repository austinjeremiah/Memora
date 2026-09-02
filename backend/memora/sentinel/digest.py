"""Sentinel's own memory -- what it already noticed.

This is the self-referential part: Sentinel reads its own prior findings out of
Sibyl, compares them to what it sees now, and writes the updated picture back.
Without it there is no NEW-vs-PERSISTING distinction, because nothing would
remember whether a finding had been announced before.

FORK 1, resolved: Sibyl scopes every read and write by tenant, and MEMORA uses
one tenant per patient, so a cross-patient digest has nowhere natural to live.
Rather than invent a new architectural concept, this reuses PatientMemory
pointed at one reserved, clearly-non-clinical id. Same facade, same quota
discipline, no new code path into Sibyl.

The reserved id must be provably incapable of colliding with a real patient.
Synthea issues UUIDs; this is not one, and a test asserts that rather than
leaving it to convention.
"""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from memora.sentinel.state_machine import FindingStatus

SENTINEL_SYSTEM_ID = "__sentinel_system__"
DIGEST_STATE_KEY_TEMPLATE = "sentinel_digest:{situation}"


@dataclass
class Finding:
    """One thing Sentinel noticed about one record."""

    patient_id: str
    kind: str
    name: str
    status: str
    gate_result: str
    reason: str
    first_seen_at: str
    last_seen_at: str
    runs_seen: int = 1
    triggered_rules: list[str] = field(default_factory=list)
    evidence_event: str | None = None
    detector: str = "delta"  # "delta" | "drift"

    @property
    def key(self) -> str:
        """Stable identity across runs -- what makes a finding 'the same one'."""
        return f"{self.patient_id}|{self.kind}|{self.name}|{self.detector}"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def system_memory():
    """The reserved pseudo-patient scope holding every situation's digest.

    NOT clinical data. Must never be listed, searched, or surfaced alongside
    real patients -- enforced at the route layer, not merely by convention here.
    """
    from memora.sibyl.client import PatientMemory

    return PatientMemory(patient_id=SENTINEL_SYSTEM_ID)


def digest_key(situation: str) -> str:
    return DIGEST_STATE_KEY_TEMPLATE.format(situation=situation)


def load_digest(situation: str) -> dict[str, dict]:
    """Prior findings for a situation, keyed by Finding.key. Empty on first run."""
    stored = system_memory().get_context(digest_key(situation))
    if not stored:
        return {}
    return stored.get("findings", {})


def save_digest(situation: str, findings: dict[str, dict],
                run_at: str | None = None) -> None:
    """Overwrite the situation's digest.

    Exactly ONE set_state call per situation per run, regardless of how many
    patients were scanned -- O(1), not O(patients). This matters against the
    measured 5,242,880-byte cap, where row count rather than payload is what
    drives store size.
    """
    system_memory().set_context(digest_key(situation), {
        "situation": situation,
        "run_at": run_at or datetime.now(UTC).isoformat(),
        "findings": findings,
    })


def merge_finding(previous: dict | None, current: Finding,
                  new_status: FindingStatus) -> Finding:
    """Carry forward what the digest already knew about this finding.

    first_seen_at and runs_seen belong to the finding's whole history, not to
    this run, so they survive; everything else reflects now.
    """
    if previous is None:
        current.status = new_status.value
        return current

    current.first_seen_at = previous.get("first_seen_at", current.first_seen_at)
    current.runs_seen = int(previous.get("runs_seen", 0)) + 1
    current.status = new_status.value
    return current
