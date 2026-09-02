"""Patient isolation is a real Sibyl tenant boundary, not a naming convention.

Two patients writing the same (kind, name) must not see each other's rows --
enforced by UNIQUE (tenant_id, category, name) at the schema level.
"""

import pytest

from memora.ontology.events import EVENT_HANDOFF, ClinicalEvent
from memora.ontology.kinds import KIND_MEDICATION, STATUS_ACTIVE
from memora.sibyl.client import PatientMemory
from memora.sibyl.keys import PatientScope, validate_patient_id

pytestmark = pytest.mark.integration


def test_same_key_different_patients_do_not_collide(store):
    a = PatientMemory("P-10482")
    b = PatientMemory("P-99999")

    a.set_fact(KIND_MEDICATION, "drug_a", {"owner": "A"}, status=STATUS_ACTIVE)
    b.set_fact(KIND_MEDICATION, "drug_a", {"owner": "B"}, status=STATUS_ACTIVE)

    assert a.get_fact_body(KIND_MEDICATION, "drug_a") == {"owner": "A"}
    assert b.get_fact_body(KIND_MEDICATION, "drug_a") == {"owner": "B"}


def test_one_patients_fact_is_invisible_to_another(store):
    a = PatientMemory("P-10482")
    b = PatientMemory("P-99999")
    a.set_fact(KIND_MEDICATION, "only_for_a", {"n": 1}, status=STATUS_ACTIVE)

    assert b.get_fact(KIND_MEDICATION, "only_for_a") is None
    assert b.list_facts(KIND_MEDICATION) == []
    assert b.search("only_for_a") == []


def test_history_is_tenant_scoped(store):
    a = PatientMemory("P-10482")
    b = PatientMemory("P-99999")
    a.log_event(ClinicalEvent(EVENT_HANDOFF, "A was admitted", "2026-01-01T00:00:00Z"))

    assert len(a.read_history()) == 1
    assert b.read_history() == []


def test_hot_state_is_tenant_scoped(store):
    a = PatientMemory("P-10482")
    b = PatientMemory("P-99999")
    a.set_context("active_situation", {"situation": "icu_to_ward"})

    assert a.get_context("active_situation") == {"situation": "icu_to_ward"}
    assert b.get_context("active_situation") is None


def test_tenant_id_derivation():
    assert PatientScope("P-10482").tenant_id == "patient-P-10482"


@pytest.mark.parametrize("bad", ["", "   ", "drug; rm -rf", 'a"b', "a|b", "x" * 513])
def test_dangerous_patient_ids_are_refused(bad):
    with pytest.raises(ValueError):
        validate_patient_id(bad)
