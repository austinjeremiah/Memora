"""Memory drift -- current state contradicting its own history.

This is the check with no equivalent anywhere else in MEMORA. The reactive path
reads WARM facts as current truth and never asks whether the journal agrees
with them. Drift asks exactly that: the store says this medication is active,
and the store also says there was a documented adverse reaction to it. Both
came from memory. They cannot both be right.

That is not a claim needing verification -- it is memory disagreeing with
itself, and no model is involved in noticing it.
"""

import logging

from memora.context.situations import ClinicianRole
from memora.evidence.resolver import EvidenceCheck, EvidenceEvent, _matching_events
from memora.gate.gate import GateDecision, evaluate_claim
from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_MEDICATION_DISCONTINUED,
    SEVERITY_CRITICAL,
)
from memora.ontology.kinds import (
    KIND_MEDICATION,
    STATUS_ACTIVE,
    STATUS_DISCONTINUED,
)
from memora.sibyl.client import PatientMemory

log = logging.getLogger("memora.sentinel")

# Journal event types that contradict a medication still being active.
_CONTRADICTS_ACTIVE_MEDICATION = frozenset({
    EVENT_ADVERSE_REACTION,
    EVENT_MEDICATION_DISCONTINUED,
})


def find_conflicting_constraint(kind: str, current_status: str | None,
                                history: tuple[EvidenceEvent, ...],
                                ) -> EvidenceEvent | None:
    """The one conflict pattern worth shipping first, deliberately narrow.

    Matches on the structured `event_type` field, never a substring check
    against a rendered event. That substring anti-pattern was already found and
    removed from the resolver in Phase 10 for over-matching and silently
    under-matching; it is not being reintroduced here.

    `history` is the tuple[EvidenceEvent, ...] returned by _matching_events --
    these are objects with attributes, not raw journal dicts. Extend this with
    one real conflict pattern at a time; do not build a generic
    "detect any disagreement" engine before a second real pattern needs it.
    """
    if kind != KIND_MEDICATION or current_status != STATUS_ACTIVE:
        return None
    for event in history:
        if event.event_type in _CONTRADICTS_ACTIVE_MEDICATION:
            return event
    return None


def check_drift(memory: PatientMemory, kind: str, name: str,
                current_status: str | None) -> GateDecision | None:
    """Compare a current WARM fact against its own COLD history.

    Returns None when memory is self-consistent for this record.

    _matching_events takes the PatientMemory and reads history itself, filtering
    structurally on the stored (related_kind, related_name) pointers -- there is
    no need to call read_history first, and no need for a second filter.
    """
    history = _matching_events(memory, kind, name)
    conflicting = find_conflicting_constraint(kind, current_status, history)
    if conflicting is None:
        return None

    evidence = EvidenceCheck(
        claim_text=(f"{kind}/{name} is recorded as '{current_status}', but the "
                    f"journal contains a {conflicting.event_type} event for it "
                    f"on {conflicting.timestamp[:10]}."),
        supported=True,
        source_kind=kind,
        source_name=name,
        fact_status=current_status,
        # EvidenceEvent objects, never raw dicts: policy._has_critical_history
        # reads event.severity as an attribute and would AttributeError on a
        # dict, surfacing as a 500 rather than a finding.
        source_events=(conflicting,),
    )
    return evaluate_claim(memory, evidence, ClinicianRole.SYSTEM)


def is_resolved_by(current_status: str | None) -> bool:
    """Whether a previously drifting medication now reads as reconciled."""
    return current_status in (STATUS_DISCONTINUED, "contraindicated")


def severity_of(decision: GateDecision) -> str:
    """Drift backed by a critical event is itself critical."""
    if any(e.severity == SEVERITY_CRITICAL for e in decision.evidence.source_events):
        return SEVERITY_CRITICAL
    return "warning"
