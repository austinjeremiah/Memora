"""Deterministic Safety Gate against a real Sibyl store.

The original plan tested this layer with mocks, and that is exactly why its
policy rule was broken: the mock returned {"status": "contraindicated"} as the
whole record, while the real SDK returns an entity ROW whose clinical payload
sits under "body" and whose lifecycle marker is the "status" column. The mocked
test passed; the real rule could never fire. Every test here uses a real store.
"""

import pytest

from memora.context.situations import ClinicianRole
from memora.evidence.resolver import resolve_claim
from memora.gate.authority import ROLE_PERMISSIONS, can_approve_handoff, has_authority
from memora.gate.gate import GateResult, evaluate_all, evaluate_claim, summarise
from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_MEDICATION_ADMINISTERED,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    ClinicalEvent,
)
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_DIAGNOSIS,
    KIND_LAB_TREND,
    KIND_MEDICATION,
    STATUS_ACTIVE,
    STATUS_CONTRAINDICATED,
    STATUS_DISCONTINUED,
    STATUS_DOCUMENTED,
)
from memora.sibyl.client import PatientMemory

pytestmark = pytest.mark.integration

PATIENT = "P-10482"


@pytest.fixture
def memory(store):
    return PatientMemory(PATIENT)


def _check(memory, kind, name, text="a claim"):
    return resolve_claim(memory, text, kind, name)


# ---- 1. evidence check --------------------------------------------------

def test_unsupported_claim_is_blocked(memory):
    evidence = _check(memory, KIND_MEDICATION, "never_existed")
    decision = evaluate_claim(memory, evidence, ClinicianRole.WARD_PHYSICIAN)
    assert decision.result is GateResult.BLOCK
    assert decision.triggered_rules == ()


def test_unsourced_claim_is_blocked(memory):
    evidence = resolve_claim(memory, "Patient is stable", None, None)
    decision = evaluate_claim(memory, evidence, ClinicianRole.WARD_PHYSICIAN)
    assert decision.result is GateResult.BLOCK
    assert "unsourced" in decision.reason


# ---- 2. authority check -------------------------------------------------

def test_role_without_permission_is_blocked(memory):
    memory.set_fact(KIND_LAB_TREND, "creatinine", {"trend": "rising"},
                    status=STATUS_ACTIVE)
    evidence = _check(memory, KIND_LAB_TREND, "creatinine")
    assert evidence.supported is True

    decision = evaluate_claim(memory, evidence, ClinicianRole.SURGEON)
    assert decision.result is GateResult.BLOCK
    assert "not authorised" in decision.reason

    # The same claim, same evidence, for a role that may see it.
    allowed = evaluate_claim(memory, evidence, ClinicianRole.ICU_PHYSICIAN)
    assert allowed.result is GateResult.ALLOW


def test_evidence_failure_takes_precedence_over_authority(memory):
    """An unsupported claim blocks on evidence, not on permissions -- the
    reason a clinician sees must name the real problem."""
    evidence = _check(memory, KIND_LAB_TREND, "does_not_exist")
    decision = evaluate_claim(memory, evidence, ClinicianRole.SURGEON)
    assert decision.result is GateResult.BLOCK
    assert "not authorised" not in decision.reason


def test_unknown_role_fails_closed(memory):
    memory.set_fact(KIND_MEDICATION, "drug_b", {"n": 1}, status=STATUS_ACTIVE)
    evidence = _check(memory, KIND_MEDICATION, "drug_b")
    assert has_authority("not_a_real_role", KIND_MEDICATION) is False
    decision = evaluate_claim(memory, evidence, "not_a_real_role")
    assert decision.result is GateResult.BLOCK


def test_authority_table_covers_every_declared_role():
    for role in ClinicianRole:
        assert role in ROLE_PERMISSIONS
    assert can_approve_handoff(ClinicianRole.SURGEON) is False
    assert can_approve_handoff(ClinicianRole.WARD_PHYSICIAN) is True


# ---- 3. policy checks ---------------------------------------------------

def test_contraindicated_medication_needs_review(memory):
    """THE REGRESSION TEST. status is a real column on the entity row; the
    mocked version of this test passed while the production path never fired."""
    memory.set_fact(KIND_MEDICATION, "drug_a", {"reason": "adverse reaction"},
                    status=STATUS_CONTRAINDICATED)
    evidence = _check(memory, KIND_MEDICATION, "drug_a", "Drug A could be used")

    assert evidence.fact_status == STATUS_CONTRAINDICATED, \
        "status must come from the row column, not the body"

    decision = evaluate_claim(memory, evidence, ClinicianRole.WARD_PHYSICIAN)
    assert decision.result is GateResult.NEEDS_REVIEW
    assert "contraindicated_record" in decision.triggered_rules


def test_status_buried_in_body_does_not_trigger_the_rule(memory):
    """Guards the inverse mistake: a body that merely says 'contraindicated'
    while the column says active is NOT a contraindication."""
    memory.set_fact(KIND_MEDICATION, "drug_c", {"status": "contraindicated"},
                    status=STATUS_ACTIVE)
    evidence = _check(memory, KIND_MEDICATION, "drug_c")
    decision = evaluate_claim(memory, evidence, ClinicianRole.WARD_PHYSICIAN)
    assert decision.result is GateResult.ALLOW


def test_discontinued_medication_needs_review(memory):
    memory.set_fact(KIND_MEDICATION, "drug_d", {"n": 1}, status=STATUS_DISCONTINUED)
    decision = evaluate_claim(memory, _check(memory, KIND_MEDICATION, "drug_d"),
                              ClinicianRole.WARD_PHYSICIAN)
    assert decision.result is GateResult.NEEDS_REVIEW
    assert "discontinued_record" in decision.triggered_rules


def test_critical_event_on_file_needs_review(memory):
    memory.set_fact(KIND_MEDICATION, "drug_e", {"n": 1}, status=STATUS_ACTIVE)
    memory.log_event(ClinicalEvent(EVENT_ADVERSE_REACTION, "Reaction to Drug E",
                                   "2026-01-04T00:00:00Z", KIND_MEDICATION,
                                   "drug_e", "ev-1", SEVERITY_CRITICAL))
    decision = evaluate_claim(memory, _check(memory, KIND_MEDICATION, "drug_e"),
                              ClinicianRole.WARD_PHYSICIAN)
    assert decision.result is GateResult.NEEDS_REVIEW
    assert "critical_event_on_file" in decision.triggered_rules


def test_non_critical_history_does_not_escalate(memory):
    memory.set_fact(KIND_MEDICATION, "drug_f", {"n": 1}, status=STATUS_ACTIVE)
    memory.log_event(ClinicalEvent(EVENT_MEDICATION_ADMINISTERED, "Drug F given",
                                   "2026-01-04T00:00:00Z", KIND_MEDICATION,
                                   "drug_f", "ev-2", SEVERITY_INFO))
    decision = evaluate_claim(memory, _check(memory, KIND_MEDICATION, "drug_f"),
                              ClinicianRole.WARD_PHYSICIAN)
    assert decision.result is GateResult.ALLOW


def test_medication_overlapping_a_documented_allergy_needs_review(memory):
    """Cross-references OTHER records for the patient, not just this claim's."""
    memory.set_fact(KIND_ALLERGY, "penicillin", {"reaction": "anaphylaxis"},
                    status=STATUS_DOCUMENTED)
    memory.set_fact(KIND_MEDICATION, "penicillin_v", {"dose": "500mg"},
                    status=STATUS_ACTIVE)
    decision = evaluate_claim(memory, _check(memory, KIND_MEDICATION, "penicillin_v"),
                              ClinicianRole.WARD_PHYSICIAN)
    assert decision.result is GateResult.NEEDS_REVIEW
    assert "documented_allergy_conflict" in decision.triggered_rules


def test_unrelated_medication_is_not_flagged_by_the_allergy_rule(memory):
    memory.set_fact(KIND_ALLERGY, "penicillin", {"reaction": "anaphylaxis"},
                    status=STATUS_DOCUMENTED)
    memory.set_fact(KIND_MEDICATION, "paracetamol", {"dose": "1g"},
                    status=STATUS_ACTIVE)
    decision = evaluate_claim(memory, _check(memory, KIND_MEDICATION, "paracetamol"),
                              ClinicianRole.WARD_PHYSICIAN)
    assert decision.result is GateResult.ALLOW


def test_every_triggered_rule_is_reported_not_just_the_first(memory):
    """A claim tripping three rules must say so -- a reviewing clinician needs
    all of them, not whichever happened to be evaluated first."""
    memory.set_fact(KIND_ALLERGY, "penicillin", {"reaction": "anaphylaxis"},
                    status=STATUS_DOCUMENTED)
    memory.set_fact(KIND_MEDICATION, "penicillin_v", {"n": 1},
                    status=STATUS_CONTRAINDICATED)
    memory.log_event(ClinicalEvent(EVENT_ADVERSE_REACTION, "Anaphylaxis",
                                   "2026-01-04T00:00:00Z", KIND_MEDICATION,
                                   "penicillin_v", "ev-3", SEVERITY_CRITICAL))
    decision = evaluate_claim(memory, _check(memory, KIND_MEDICATION, "penicillin_v"),
                              ClinicianRole.WARD_PHYSICIAN)
    assert decision.result is GateResult.NEEDS_REVIEW
    assert set(decision.triggered_rules) == {
        "contraindicated_record", "critical_event_on_file",
        "documented_allergy_conflict",
    }


# ---- the clean path -----------------------------------------------------

def test_supported_authorised_unflagged_claim_is_allowed(memory):
    memory.set_fact(KIND_MEDICATION, "drug_b", {"dose": "5mg"}, status=STATUS_ACTIVE)
    decision = evaluate_claim(memory, _check(memory, KIND_MEDICATION, "drug_b"),
                              ClinicianRole.WARD_PHYSICIAN)
    assert decision.result is GateResult.ALLOW
    assert decision.triggered_rules == ()
    assert decision.is_presentable is False


# ---- batch + determinism ------------------------------------------------

def test_evaluate_all_and_summarise(memory):
    memory.set_fact(KIND_MEDICATION, "ok_drug", {"n": 1}, status=STATUS_ACTIVE)
    memory.set_fact(KIND_MEDICATION, "bad_drug", {"n": 2},
                    status=STATUS_CONTRAINDICATED)
    memory.set_fact(KIND_DIAGNOSIS, "sepsis", {"n": 3}, status=STATUS_ACTIVE)

    checks = [
        _check(memory, KIND_MEDICATION, "ok_drug"),
        _check(memory, KIND_MEDICATION, "bad_drug"),
        _check(memory, KIND_MEDICATION, "ghost_drug"),
        _check(memory, KIND_DIAGNOSIS, "sepsis"),
    ]
    decisions = evaluate_all(memory, checks, ClinicianRole.SURGEON)
    assert summarise(decisions) == {"ALLOW": 1, "NEEDS_REVIEW": 1, "BLOCK": 2}


def test_gate_is_deterministic(memory):
    memory.set_fact(KIND_MEDICATION, "drug_a", {"n": 1},
                    status=STATUS_CONTRAINDICATED)
    evidence = _check(memory, KIND_MEDICATION, "drug_a")
    first = evaluate_claim(memory, evidence, ClinicianRole.WARD_PHYSICIAN)
    second = evaluate_claim(memory, evidence, ClinicianRole.WARD_PHYSICIAN)
    assert first == second
