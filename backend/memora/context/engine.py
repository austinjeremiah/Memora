"""Situation-aware retrieval.

Two stages, deliberately separated:

  compile_plan()  situation + role + patient -> a bounded, deterministic plan.
                  Pure: no I/O, no clock, no randomness. Same inputs always
                  produce an equal RetrievalPlan.

  execute_plan()  runs that plan against Sibyl and returns what it found.
                  Faithful and bounded; it does not rank by relevance or decide
                  what is true -- that is the Evidence Resolver's job.

Both differ from the original plan in two ways that matter:

  * Enumeration uses list_facts(kind), a real indexed query. The plan called for
    search_entities(kind) as a stand-in for "list everything of this kind", with
    a fallback index-entity design if it under-returned. It would have: FTS5
    ranks and caps, so a patient's third medication could silently vanish.

  * History is filtered on the structured extra["event_type"] field, not by
    substring-matching the repr of a row. The latter would match a drug whose
    NAME happened to contain an event-type word, and would miss anything whose
    formatting changed.
"""

from dataclasses import dataclass, field

from memora.config import settings
from memora.context.situations import (
    SITUATION_FOCUS,
    ClinicianRole,
    Situation,
)
from memora.ontology.events import SEVERITY_CRITICAL, ClinicalEvent
from memora.ontology.kinds import STATE_KEY_ACTIVE_SITUATION
from memora.sibyl.client import PatientMemory


@dataclass(frozen=True)
class RetrievalPlan:
    """What to fetch. Frozen and built from tuples so equality is structural --
    that is what the determinism test asserts."""

    patient_id: str
    situation: Situation
    role: ClinicianRole
    task: str
    kinds_to_check: tuple[str, ...]
    event_types_to_check: tuple[str, ...]
    max_items: int


@dataclass
class RetrievedContext:
    """What the plan actually found."""

    plan: RetrievalPlan
    facts: dict[str, list[dict]] = field(default_factory=dict)
    history: list[ClinicalEvent] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(self.facts.values()) and not self.history

    def fact_count(self) -> int:
        return sum(len(v) for v in self.facts.values())


def compile_plan(
    patient_id: str,
    situation: Situation,
    role: ClinicianRole,
    *,
    max_items: int | None = None,
) -> RetrievalPlan:
    """Pure function: same inputs, same plan, every time."""
    focus = SITUATION_FOCUS[situation]
    return RetrievalPlan(
        patient_id=patient_id,
        situation=situation,
        role=role,
        task=focus.task,
        kinds_to_check=focus.kinds,
        event_types_to_check=focus.event_types,
        max_items=settings.max_evidence_items if max_items is None else max_items,
    )


def _history_rank(event: ClinicalEvent) -> tuple[int, str]:
    """Order history by clinical weight, then recency.

    Critical events sort first deliberately. Under a per-situation item cap, a
    documented adverse reaction must never be the row that falls off the end
    because three routine lab results happened to be more recent -- that is the
    exact failure this whole product exists to prevent. Recency breaks ties.
    """
    is_critical = 0 if event.severity == SEVERITY_CRITICAL else 1
    return (is_critical, event.timestamp)


def execute_plan(plan: RetrievalPlan) -> RetrievedContext:
    """Run the plan against Sibyl.

    require_data=True: a healthy store holding nothing for this patient is a
    different failure from the memory layer being gone, and both must be loud.
    """
    memory = PatientMemory(plan.patient_id, require_data=True)

    # Record the active situation in HOT state, so "what this clinician is
    # currently doing" is genuinely part of memory and inspectable via
    # get_context -- not a Python variable that dies with the request.
    memory.set_context(
        STATE_KEY_ACTIVE_SITUATION,
        {
            "situation": plan.situation.value,
            "role": plan.role.value,
            "task": plan.task,
        },
    )

    facts: dict[str, list[dict]] = {}
    for kind in plan.kinds_to_check:
        rows = memory.list_facts(kind)
        # Stable ordering: list_entities sorts by updated_at DESC, and bulk
        # ingestion can write several rows inside the same millisecond, so name
        # is the tiebreak that keeps repeated runs identical.
        rows.sort(key=lambda r: (r["updated_at"], r["name"]), reverse=True)
        facts[kind] = rows[: plan.max_items]

    wanted = set(plan.event_types_to_check)
    events = [ClinicalEvent.from_record(r) for r in memory.read_history()]
    relevant = [e for e in events if e.event_type in wanted]
    relevant.sort(key=_history_rank)
    selected = relevant[: plan.max_items]
    # Present the selection in clinical order once the cap has been applied.
    selected.sort(key=lambda e: e.timestamp)

    return RetrievedContext(plan=plan, facts=facts, history=selected)
