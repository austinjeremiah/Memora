"""Delta detection -- a WARM fact changed in a way that matters.

NO LLM IS INVOLVED, ANYWHERE IN THIS MODULE OR ITS CALLERS. That is the
architectural point of Sentinel: the EvidenceCheck is built directly from a
confirmed Sibyl write, so `supported=True` is true BY CONSTRUCTION -- this is
the record itself, not a model's guess about the record. It then goes through
the same unmodified Gate the reactive path uses.

So "the model can be wrong, the gate can't" holds for an entire mode of the
system with literally no model present to be wrong.
"""

import logging

from memora.context.situations import ClinicianRole
from memora.evidence.resolver import EvidenceCheck, EvidenceEvent
from memora.gate.gate import GateDecision, evaluate_claim
from memora.ingest.change_detector import _VOLATILE_FIELDS
from memora.ontology.kinds import ALL_KINDS
from memora.sibyl.client import PatientMemory

log = logging.getLogger("memora.sentinel")


def _material(body: object) -> object:
    """A record's clinically meaningful content, ignoring bookkeeping fields."""
    if not isinstance(body, dict):
        return body
    return {k: v for k, v in body.items() if k not in _VOLATILE_FIELDS}


def is_policy_relevant_change(kind: str, previous: dict | None,
                              current: dict | None,
                              previous_status: str | None = None,
                              current_status: str | None = None) -> bool:
    """Cheap filter before the Gate runs.

    Two things make a change worth judging: the record's content changed, or
    its lifecycle status changed.

    Do NOT write this as `previous != current`. Stored bodies carry `last_seen`,
    which changes on every observation, so a whole-body comparison fires on
    every routine re-confirmation and Sentinel raises findings for records that
    did not clinically change. This is the same bug already hit in ingestion,
    where it turned 318 of 400 events into spurious transitions. The exclusion
    set is imported rather than re-derived so there is one definition of
    "volatile", not two that can drift apart.

    And status must be compared SEPARATELY from the body. A medication moving
    from 'active' to 'contraindicated' is the most clinically significant delta
    the system can see, and it routinely happens with an unchanged body --
    status lives in its own indexed column, not in the payload. Comparing only
    bodies misses it entirely, which a test caught here rather than a demo.
    """
    if kind not in ALL_KINDS:
        return False
    if previous is None:
        return True  # first sighting of a tracked record is always worth checking
    if previous_status != current_status:
        return True
    return _material(previous) != _material(current)


def _describe(kind: str, name: str, previous: dict | None,
              current: dict | None, previous_status: str | None,
              current_status: str | None) -> str:
    if previous is None:
        return f"New {kind} record '{name}' recorded with status '{current_status}'."
    if previous_status != current_status:
        return (f"{kind}/{name} status changed from "
                f"'{previous_status}' to '{current_status}'.")
    return f"{kind}/{name} content changed while status remained '{current_status}'."


def evaluate_delta(memory: PatientMemory, kind: str, name: str,
                   previous: dict | None, current: dict | None,
                   previous_status: str | None = None,
                   current_status: str | None = None,
                   event_severity: str | None = None) -> GateDecision | None:
    """Judge one WARM change. Returns None when the change is not worth judging.

    `previous`/`current` are entity BODIES, not rows -- the caller already has
    both, so Sentinel does not re-read Sibyl to re-derive what changed. That
    would be duplicated work and a second place the change logic could drift
    out of step with the first.
    """
    if not is_policy_relevant_change(kind, previous, current,
                                     previous_status, current_status):
        return None

    source_events: tuple[EvidenceEvent, ...] = ()
    if event_severity is not None:
        source_events = (EvidenceEvent(
            source_id=None,
            event_type="sentinel_delta",
            timestamp=str((current or {}).get("last_seen", "")),
            summary=_describe(kind, name, previous, current,
                              previous_status, current_status),
            severity=event_severity,
        ),)

    evidence = EvidenceCheck(
        claim_text=_describe(kind, name, previous, current,
                             previous_status, current_status),
        supported=True,          # by construction: this IS the persisted record
        source_kind=kind,
        source_name=name,
        fact_status=current_status,
        fact_body=current,
        source_events=source_events,
    )

    # SYSTEM, never None: has_authority(None, kind) is False, so a None role
    # would BLOCK every finding on authority before any policy rule ran.
    return evaluate_claim(memory, evidence, ClinicianRole.SYSTEM)
