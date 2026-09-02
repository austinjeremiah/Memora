"""Declared clinical policy rules.

Deterministic and explicit: each rule is a small typed object with a named
predicate, not a lambda whose signature has to be introspected at call time to
work out what to pass it. An earlier draft did exactly that -- it inspected
__code__.co_varnames to decide whether a rule wanted a fact or an evidence
check, and swallowed any exception the predicate raised. A rule that silently
never fires is worse than no rule, because the output still looks gated.

Rules receive the EvidenceCheck (which already carries the record's status,
body and cited events, all from a real Sibyl read) plus the PatientMemory, so a
rule can cross-reference other records for the patient.

Scope note: these demonstrate a working policy mechanism. They are not a
clinical decision support system, and the allergy rule in particular is a
name-overlap heuristic, not real drug-allergy interaction checking.
"""

from collections.abc import Callable
from dataclasses import dataclass

from memora.evidence.resolver import EvidenceCheck
from memora.ontology.events import SEVERITY_CRITICAL
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_MEDICATION,
    STATUS_CONTRAINDICATED,
    STATUS_DISCONTINUED,
)
from memora.sibyl.client import PatientMemory


@dataclass(frozen=True)
class PolicyRule:
    name: str
    description: str
    escalates_to: str            # GateResult value this rule forces
    predicate: Callable[[EvidenceCheck, PatientMemory], bool]

    def triggers(self, evidence: EvidenceCheck, memory: PatientMemory) -> bool:
        return self.predicate(evidence, memory)


# ---- predicates ---------------------------------------------------------

def _is_contraindicated(evidence: EvidenceCheck, _memory: PatientMemory) -> bool:
    """A record explicitly marked contraindicated can never pass silently."""
    return evidence.fact_status == STATUS_CONTRAINDICATED


def _is_discontinued(evidence: EvidenceCheck, _memory: PatientMemory) -> bool:
    """A discontinued medication presented as current needs a human to look."""
    return evidence.fact_status == STATUS_DISCONTINUED


def _has_critical_history(evidence: EvidenceCheck, _memory: PatientMemory) -> bool:
    """Anything with a critical event on file gets surfaced, never summarised
    away -- this is the adverse-reaction case the whole product exists for."""
    return any(event.severity == SEVERITY_CRITICAL for event in evidence.source_events)


def _conflicts_with_documented_allergy(evidence: EvidenceCheck,
                                       memory: PatientMemory) -> bool:
    """Flag a medication claim when a documented allergy shares its name stem.

    Name-overlap only. A real system would resolve ingredients through a drug
    ontology; this demonstrates the cross-referencing mechanism, and it reads
    other records for the patient rather than only the claim's own evidence.
    """
    if evidence.source_kind != KIND_MEDICATION or not evidence.source_name:
        return False
    medication = evidence.source_name.lower()
    for allergy in memory.list_facts(KIND_ALLERGY):
        stem = str(allergy["name"]).lower().split("_")[0]
        if len(stem) >= 4 and (stem in medication or medication.split("_")[0] == stem):
            return True
    return False


# ---- the declared rule set ---------------------------------------------

POLICY_RULES: tuple[PolicyRule, ...] = (
    PolicyRule(
        name="contraindicated_record",
        description="A record marked contraindicated must be flagged, never presented as safe.",
        escalates_to="NEEDS_REVIEW",
        predicate=_is_contraindicated,
    ),
    PolicyRule(
        name="discontinued_record",
        description="A discontinued record must not be presented as current without review.",
        escalates_to="NEEDS_REVIEW",
        predicate=_is_discontinued,
    ),
    PolicyRule(
        name="critical_event_on_file",
        description="A record with a critical event in its history must be surfaced explicitly.",
        escalates_to="NEEDS_REVIEW",
        predicate=_has_critical_history,
    ),
    PolicyRule(
        name="documented_allergy_conflict",
        description="A medication that overlaps a documented allergy must be reviewed.",
        escalates_to="NEEDS_REVIEW",
        predicate=_conflicts_with_documented_allergy,
    ),
)
