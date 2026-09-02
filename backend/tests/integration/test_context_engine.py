"""Context Engine against a real Sibyl store.

The claim under test is MEMORA's central one: the SAME patient memory yields a
DIFFERENT relevant subset depending on the clinical situation. That is asserted
here on real data, not asserted in a slide.
"""

import pytest

from memora.context.engine import compile_plan, execute_plan
from memora.context.situations import SITUATION_FOCUS, ClinicianRole, Situation
from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_DIAGNOSIS_MADE,
    EVENT_LAB_RESULT,
    EVENT_MEDICATION_ADMINISTERED,
    EVENT_MEDICATION_DISCONTINUED,
    EVENT_PROCEDURE_PERFORMED,
    SEVERITY_CRITICAL,
    ClinicalEvent,
)
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_DIAGNOSIS,
    KIND_LAB_TREND,
    KIND_MEDICATION,
    KIND_PROCEDURE,
    STATE_KEY_ACTIVE_SITUATION,
    STATUS_ACTIVE,
    STATUS_CONTRAINDICATED,
    STATUS_DOCUMENTED,
    STATUS_PERFORMED,
)
from memora.sibyl.client import PatientMemory
from memora.sibyl.errors import SibylPatientUnknownError, SibylUnavailableError

pytestmark = pytest.mark.integration

PATIENT = "P-10482"


@pytest.fixture
def seeded(store):
    """One patient with genuinely cross-situational history."""
    m = PatientMemory(PATIENT)

    m.set_fact(KIND_MEDICATION, "drug_a", {"reason": "adverse reaction"},
               status=STATUS_CONTRAINDICATED)
    m.set_fact(KIND_MEDICATION, "drug_b", {"dose": "5mg"}, status=STATUS_ACTIVE)
    m.set_fact(KIND_ALLERGY, "penicillin", {"reaction": "anaphylaxis"},
               status=STATUS_DOCUMENTED)
    m.set_fact(KIND_DIAGNOSIS, "sepsis", {"onset": "2026-01-01"}, status=STATUS_ACTIVE)
    m.set_fact(KIND_LAB_TREND, "creatinine", {"trend": "rising"}, status=STATUS_ACTIVE)
    m.set_fact(KIND_PROCEDURE, "central_line", {"site": "right IJ"},
               status=STATUS_PERFORMED)

    for e in [
        ClinicalEvent(EVENT_MEDICATION_ADMINISTERED, "Drug A administered",
                      "2026-01-02T08:00:00Z", KIND_MEDICATION, "drug_a", "s1"),
        ClinicalEvent(EVENT_ADVERSE_REACTION, "Adverse reaction to Drug A",
                      "2026-01-04T14:30:00Z", KIND_MEDICATION, "drug_a", "s2",
                      SEVERITY_CRITICAL),
        ClinicalEvent(EVENT_MEDICATION_DISCONTINUED, "Drug A discontinued",
                      "2026-01-04T16:00:00Z", KIND_MEDICATION, "drug_a", "s3",
                      SEVERITY_CRITICAL),
        ClinicalEvent(EVENT_LAB_RESULT, "Creatinine 2.1 rising",
                      "2026-01-05T06:00:00Z", KIND_LAB_TREND, "creatinine", "s4"),
        ClinicalEvent(EVENT_PROCEDURE_PERFORMED, "Central line placed",
                      "2026-01-03T11:00:00Z", KIND_PROCEDURE, "central_line", "s5"),
        ClinicalEvent(EVENT_DIAGNOSIS_MADE, "Sepsis diagnosed",
                      "2026-01-01T09:00:00Z", KIND_DIAGNOSIS, "sepsis", "s6"),
    ]:
        m.log_event(e)
    return store


# ---- compile_plan: purity + determinism ---------------------------------

def test_compile_plan_is_deterministic():
    a = compile_plan(PATIENT, Situation.ICU_TO_WARD, ClinicianRole.WARD_PHYSICIAN)
    b = compile_plan(PATIENT, Situation.ICU_TO_WARD, ClinicianRole.WARD_PHYSICIAN)
    assert a == b
    assert hash(a) == hash(b)


def test_compile_plan_needs_no_store():
    """It is pure -- no fixture, no database, no I/O of any kind."""
    plan = compile_plan(PATIENT, Situation.DISCHARGE, ClinicianRole.WARD_PHYSICIAN)
    assert plan.task == "continuity_of_care"


@pytest.mark.parametrize("situation", list(Situation))
def test_every_situation_compiles_from_the_focus_table(situation):
    plan = compile_plan(PATIENT, situation, ClinicianRole.WARD_PHYSICIAN)
    focus = SITUATION_FOCUS[situation]
    assert plan.kinds_to_check == focus.kinds
    assert plan.event_types_to_check == focus.event_types
    assert plan.task == focus.task


def test_different_situations_compile_to_different_plans():
    icu = compile_plan(PATIENT, Situation.ICU_TO_WARD, ClinicianRole.WARD_PHYSICIAN)
    preop = compile_plan(PATIENT, Situation.PRE_OPERATIVE, ClinicianRole.SURGEON)
    assert icu != preop
    assert set(icu.kinds_to_check) != set(preop.kinds_to_check)


# ---- execute_plan: the core innovation claim ----------------------------

def test_same_memory_different_situation_yields_different_subset(seeded):
    """One patient, one store, two situations, two genuinely different views."""
    icu = execute_plan(compile_plan(PATIENT, Situation.ICU_TO_WARD,
                                    ClinicianRole.WARD_PHYSICIAN))
    preop = execute_plan(compile_plan(PATIENT, Situation.PRE_OPERATIVE,
                                      ClinicianRole.SURGEON))

    # ICU->ward reconciles medications and labs; pre-op cares about procedures.
    assert KIND_LAB_TREND in icu.facts and KIND_LAB_TREND not in preop.facts
    assert KIND_PROCEDURE in preop.facts and KIND_PROCEDURE not in icu.facts

    icu_events = {e.event_type for e in icu.history}
    preop_events = {e.event_type for e in preop.history}
    assert EVENT_LAB_RESULT in icu_events
    assert EVENT_LAB_RESULT not in preop_events
    assert EVENT_PROCEDURE_PERFORMED in preop_events
    # The adverse reaction is load-bearing in BOTH -- it must never be situational.
    assert EVENT_ADVERSE_REACTION in icu_events
    assert EVENT_ADVERSE_REACTION in preop_events


def test_execute_plan_is_reproducible(seeded):
    plan = compile_plan(PATIENT, Situation.ICU_TO_WARD, ClinicianRole.WARD_PHYSICIAN)
    first = execute_plan(plan)
    second = execute_plan(plan)
    assert [e.source_id for e in first.history] == [e.source_id for e in second.history]
    assert {k: [r["name"] for r in v] for k, v in first.facts.items()} == \
           {k: [r["name"] for r in v] for k, v in second.facts.items()}


def test_history_is_filtered_structurally_not_by_substring(seeded):
    """Every returned event's type must be one the plan actually asked for."""
    plan = compile_plan(PATIENT, Situation.ICU_TO_WARD, ClinicianRole.WARD_PHYSICIAN)
    ctx = execute_plan(plan)
    assert ctx.history
    for event in ctx.history:
        assert event.event_type in plan.event_types_to_check


def test_history_is_returned_in_clinical_order(seeded):
    ctx = execute_plan(compile_plan(PATIENT, Situation.ICU_TO_WARD,
                                    ClinicianRole.WARD_PHYSICIAN))
    stamps = [e.timestamp for e in ctx.history]
    assert stamps == sorted(stamps)


def test_facts_carry_body_and_status_through(seeded):
    ctx = execute_plan(compile_plan(PATIENT, Situation.ICU_TO_WARD,
                                    ClinicianRole.WARD_PHYSICIAN))
    meds = {r["name"]: r for r in ctx.facts[KIND_MEDICATION]}
    assert meds["drug_a"]["status"] == STATUS_CONTRAINDICATED
    assert meds["drug_a"]["body"]["reason"] == "adverse reaction"


def test_active_situation_is_written_to_hot_state(seeded):
    execute_plan(compile_plan(PATIENT, Situation.PRE_OPERATIVE, ClinicianRole.SURGEON))
    context = PatientMemory(PATIENT).get_context(STATE_KEY_ACTIVE_SITUATION)
    assert context == {
        "situation": "pre_operative",
        "role": "surgeon",
        "task": "pre_operative_review",
    }


def test_critical_events_survive_the_item_cap(store):
    """A documented adverse reaction must not be pushed out by routine noise.

    Twenty recent lab results, one older critical reaction, cap of 3.
    """
    m = PatientMemory(PATIENT)
    for i in range(20):
        m.log_event(ClinicalEvent(EVENT_LAB_RESULT, f"routine lab {i}",
                                  f"2026-02-{i + 1:02d}T00:00:00Z"))
    m.log_event(ClinicalEvent(EVENT_ADVERSE_REACTION, "Adverse reaction to Drug A",
                              "2026-01-04T14:30:00Z", KIND_MEDICATION, "drug_a",
                              "crit-1", SEVERITY_CRITICAL))

    plan = compile_plan(PATIENT, Situation.ICU_TO_WARD,
                        ClinicianRole.WARD_PHYSICIAN, max_items=3)
    ctx = execute_plan(plan)

    assert len(ctx.history) == 3
    assert any(e.severity == SEVERITY_CRITICAL for e in ctx.history), \
        "the critical adverse reaction was dropped by the cap"


def test_enumeration_is_complete_not_fts_ranked(store):
    """Twelve medications, cap of 8 -- all twelve must be reachable, and the
    cap must be what limits the result, not FTS ranking."""
    m = PatientMemory(PATIENT)
    for i in range(12):
        m.set_fact(KIND_MEDICATION, f"drug_{i:02d}", {"n": i}, status=STATUS_ACTIVE)

    assert len(m.list_facts(KIND_MEDICATION)) == 12
    ctx = execute_plan(compile_plan(PATIENT, Situation.ICU_TO_WARD,
                                    ClinicianRole.WARD_PHYSICIAN, max_items=8))
    assert len(ctx.facts[KIND_MEDICATION]) == 8


# ---- failure modes stay loud --------------------------------------------

def test_execute_plan_refuses_when_memory_layer_is_deleted(seeded):
    seeded.unlink()
    plan = compile_plan(PATIENT, Situation.ICU_TO_WARD, ClinicianRole.WARD_PHYSICIAN)
    with pytest.raises(SibylUnavailableError):
        execute_plan(plan)


def test_execute_plan_refuses_an_unknown_patient(seeded):
    plan = compile_plan("P-NOBODY", Situation.ICU_TO_WARD, ClinicianRole.WARD_PHYSICIAN)
    with pytest.raises(SibylPatientUnknownError):
        execute_plan(plan)
