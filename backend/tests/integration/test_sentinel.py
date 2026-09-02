"""Sentinel against a real Sibyl store. No mocks, and no LLM anywhere.

The point under test is that a whole detection mode of MEMORA runs with no
model present -- so if any of this passed while calling out to Groq, the
architecture claim would be false.
"""

import pytest

from memora.context.situations import ClinicianRole, Situation
from memora.gate.gate import GateResult
from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_MEDICATION_ADMINISTERED,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    ClinicalEvent,
)
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_MEDICATION,
    STATUS_ACTIVE,
    STATUS_CONTRAINDICATED,
    STATUS_DISCONTINUED,
)
from memora.sentinel.digest import (
    SENTINEL_SYSTEM_ID,
    Finding,
    load_digest,
    save_digest,
)
from memora.sentinel.drift import check_drift, find_conflicting_constraint
from memora.sentinel.runner import since_last_review, sweep
from memora.sentinel.scan import evaluate_delta, is_policy_relevant_change
from memora.sentinel.state_machine import FindingStatus
from memora.sibyl.client import PatientMemory

pytestmark = pytest.mark.integration

PATIENT = "P-SENTINEL"


@pytest.fixture
def drifting(store):
    """A patient whose memory contradicts itself: an ACTIVE medication that
    also has a documented adverse reaction in its own journal."""
    m = PatientMemory(PATIENT)
    m.set_fact(KIND_MEDICATION, "drug_a", {"label": "Drug A"}, status=STATUS_ACTIVE)
    m.log_event(ClinicalEvent(EVENT_MEDICATION_ADMINISTERED, "Drug A given",
                              "2026-01-02T08:00:00Z", KIND_MEDICATION, "drug_a",
                              "ev-1", SEVERITY_INFO))
    m.log_event(ClinicalEvent(EVENT_ADVERSE_REACTION, "Adverse reaction to Drug A",
                              "2026-01-04T14:30:00Z", KIND_MEDICATION, "drug_a",
                              "ev-2", SEVERITY_CRITICAL))
    return m


# ---- the drift check ----------------------------------------------------

def test_memory_contradicting_itself_is_detected(drifting):
    """WARM says active; COLD says it caused a reaction. Both came from memory."""
    decision = check_drift(drifting, KIND_MEDICATION, "drug_a", STATUS_ACTIVE)
    assert decision is not None
    assert decision.result is not GateResult.ALLOW
    assert "conflicts" in decision.evidence.claim_text or "journal" in decision.evidence.claim_text


def test_drift_finding_carries_the_conflicting_event_as_evidence(drifting):
    decision = check_drift(drifting, KIND_MEDICATION, "drug_a", STATUS_ACTIVE)
    assert decision.evidence.source_events
    event = decision.evidence.source_events[0]
    assert event.event_type == EVENT_ADVERSE_REACTION
    assert event.source_id == "ev-2"
    # EvidenceEvent objects, not raw dicts -- policy._has_critical_history does
    # attribute access and would AttributeError on a dict.
    assert event.severity == SEVERITY_CRITICAL


def test_critical_drift_triggers_the_existing_policy_rule(drifting):
    """Sentinel reuses the unmodified Gate -- it does not carry its own rules."""
    decision = check_drift(drifting, KIND_MEDICATION, "drug_a", STATUS_ACTIVE)
    assert "critical_event_on_file" in decision.triggered_rules


def test_reconciled_medication_no_longer_drifts(drifting):
    """Once the contradiction is resolved in memory, the finding stops."""
    drifting.set_fact(KIND_MEDICATION, "drug_a", {"label": "Drug A"},
                      status=STATUS_DISCONTINUED)
    assert check_drift(drifting, KIND_MEDICATION, "drug_a", STATUS_DISCONTINUED) is None


def test_self_consistent_memory_produces_no_finding(store):
    m = PatientMemory(PATIENT)
    m.set_fact(KIND_MEDICATION, "drug_b", {"label": "Drug B"}, status=STATUS_ACTIVE)
    m.log_event(ClinicalEvent(EVENT_MEDICATION_ADMINISTERED, "Drug B given",
                              "2026-01-02T08:00:00Z", KIND_MEDICATION, "drug_b",
                              "ev-3", SEVERITY_INFO))
    assert check_drift(m, KIND_MEDICATION, "drug_b", STATUS_ACTIVE) is None


def test_conflict_matching_is_structural_not_substring(store):
    """An event whose PROSE mentions a reaction, but whose type does not, must
    not trigger drift -- the substring anti-pattern removed in Phase 10."""
    m = PatientMemory(PATIENT)
    m.set_fact(KIND_MEDICATION, "drug_c", {"label": "Drug C"}, status=STATUS_ACTIVE)
    m.log_event(ClinicalEvent(EVENT_MEDICATION_ADMINISTERED,
                              "Given despite prior adverse_reaction elsewhere",
                              "2026-01-02T08:00:00Z", KIND_MEDICATION, "drug_c",
                              "ev-4", SEVERITY_INFO))
    assert check_drift(m, KIND_MEDICATION, "drug_c", STATUS_ACTIVE) is None


def test_find_conflicting_constraint_ignores_non_medications():
    assert find_conflicting_constraint(KIND_ALLERGY, STATUS_ACTIVE, ()) is None


# ---- no LLM in the detection path ---------------------------------------

def test_detection_path_never_calls_a_model(drifting, monkeypatch):
    """If Sentinel ever reached for the LLM, this would raise."""
    from memora.llm import propose

    def explode(*_a, **_k):
        raise AssertionError("Sentinel called the LLM -- the architecture claim is false")

    monkeypatch.setattr(propose, "propose_claims", explode)
    assert check_drift(drifting, KIND_MEDICATION, "drug_a", STATUS_ACTIVE) is not None


# ---- delta detection ----------------------------------------------------

def test_routine_reconfirmation_is_not_a_finding():
    """last_seen changes on every observation. Comparing whole bodies would
    raise a finding for every re-confirmed fact -- the ingestion bug again."""
    previous = {"label": "Drug A", "last_seen": "2026-01-01T00:00:00Z"}
    current = {"label": "Drug A", "last_seen": "2026-06-01T00:00:00Z"}
    assert is_policy_relevant_change(KIND_MEDICATION, previous, current) is False


def test_a_real_content_change_is_relevant():
    assert is_policy_relevant_change(
        KIND_MEDICATION,
        {"label": "Drug A", "last_seen": "2026-01-01"},
        {"label": "Drug A 5mg", "last_seen": "2026-01-01"}) is True


def test_untracked_kind_is_ignored():
    assert is_policy_relevant_change("astrology", None, {"sign": "leo"}) is False


def test_delta_on_a_contraindicated_status_is_flagged(store):
    m = PatientMemory(PATIENT)
    m.set_fact(KIND_MEDICATION, "drug_d", {"label": "D"}, status=STATUS_CONTRAINDICATED)
    decision = evaluate_delta(
        m, KIND_MEDICATION, "drug_d",
        previous={"label": "D"}, current={"label": "D"},
        previous_status=STATUS_ACTIVE, current_status=STATUS_CONTRAINDICATED)
    assert decision is not None
    assert decision.result is GateResult.NEEDS_REVIEW
    assert "contraindicated_record" in decision.triggered_rules


# ---- the state machine over a real sweep --------------------------------

def test_sweep_reports_new_then_persisting_then_resolved(drifting):
    first = sweep(Situation.ICU_TO_WARD, [PATIENT])
    assert first.patients_scanned == 1
    assert first.records_checked > 0
    hits = [f for f in first.findings if f.name == "drug_a"]
    assert len(hits) == 1 and hits[0].status == FindingStatus.NEW.value

    second = sweep(Situation.ICU_TO_WARD, [PATIENT])
    hits = [f for f in second.findings if f.name == "drug_a"]
    assert hits[0].status == FindingStatus.PERSISTING.value, "re-announced as NEW"
    assert hits[0].runs_seen == 2
    assert hits[0].first_seen_at == first.findings[0].first_seen_at

    # Reconcile the contradiction; the next sweep reports it resolved.
    drifting.set_fact(KIND_MEDICATION, "drug_a", {"label": "Drug A"},
                      status=STATUS_DISCONTINUED)
    third = sweep(Situation.ICU_TO_WARD, [PATIENT])
    hits = [f for f in third.findings if f.name == "drug_a"]
    assert hits[0].status == FindingStatus.RESOLVED.value

    # ...and is not carried forever as stale state.
    fourth = sweep(Situation.ICU_TO_WARD, [PATIENT])
    assert not [f for f in fourth.findings if f.name == "drug_a"]


def test_sweep_escalates_after_the_threshold(drifting):
    for _ in range(3):
        run = sweep(Situation.ICU_TO_WARD, [PATIENT], escalation_threshold=3)
    hits = [f for f in run.findings if f.name == "drug_a"]
    assert hits[0].status == FindingStatus.ESCALATED.value


def test_persisting_findings_are_not_announced(drifting):
    sweep(Situation.ICU_TO_WARD, [PATIENT])
    second = sweep(Situation.ICU_TO_WARD, [PATIENT])
    assert second.findings, "the finding should still be tracked"
    assert not second.announceable(), "a persisting finding must not re-alert"


# ---- the digest ---------------------------------------------------------

def test_digest_write_is_one_row_regardless_of_patient_count(store):
    """O(1) writes per situation per run -- row count drives store size."""
    for i in range(5):
        m = PatientMemory(f"P-BULK-{i}")
        m.set_fact(KIND_MEDICATION, "drug_a", {"label": "A"}, status=STATUS_ACTIVE)
        m.log_event(ClinicalEvent(EVENT_ADVERSE_REACTION, "reaction",
                                  "2026-01-04T00:00:00Z", KIND_MEDICATION,
                                  "drug_a", f"ev-{i}", SEVERITY_CRITICAL))

    import sqlite3
    sweep(Situation.ICU_TO_WARD, [f"P-BULK-{i}" for i in range(5)])
    con = sqlite3.connect(store)
    rows = con.execute(
        "SELECT COUNT(*) FROM state_documents WHERE tenant_id=?",
        (f"patient-{SENTINEL_SYSTEM_ID}",)).fetchone()[0]
    assert rows == 1, "digest must be one row per situation, not one per patient"


def test_digest_survives_a_fresh_client(drifting):
    """Sentinel's own memory persists the same way patient memory does."""
    sweep(Situation.ICU_TO_WARD, [PATIENT])
    assert load_digest(Situation.ICU_TO_WARD.value), "digest did not persist"


def test_since_last_review_is_a_pure_read(drifting):
    sweep(Situation.ICU_TO_WARD, [PATIENT])
    view = since_last_review(Situation.ICU_TO_WARD, PATIENT)
    assert view["new"] and not view["persisting"]
    assert view["new"][0]["name"] == "drug_a"


def test_digest_isolates_situations(drifting):
    sweep(Situation.ICU_TO_WARD, [PATIENT])
    assert load_digest(Situation.PRE_OPERATIVE.value) == {}


def test_saved_digest_round_trips(store):
    finding = Finding(patient_id=PATIENT, kind=KIND_MEDICATION, name="drug_a",
                      status=FindingStatus.NEW.value, gate_result="NEEDS_REVIEW",
                      reason="r", first_seen_at="t", last_seen_at="t")
    save_digest("icu_to_ward", {finding.key: finding.as_dict()})
    assert load_digest("icu_to_ward")[finding.key]["name"] == "drug_a"


# ---- authority is applied, not bypassed ---------------------------------

def test_sentinel_uses_the_system_role_and_cannot_approve():
    from memora.gate.authority import can_approve_handoff, has_authority
    assert has_authority(ClinicianRole.SYSTEM, KIND_MEDICATION) is True
    assert can_approve_handoff(ClinicianRole.SYSTEM) is False
