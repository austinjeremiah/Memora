"""Synthea parsing and ingestion, against REAL generated bundles.

These tests read actual Synthea FHIR output. If it has not been generated they
skip rather than fall back to a fabricated bundle -- a hand-written fixture
would encode my assumptions about FHIR, which is exactly the mistake this
parser was written to avoid. Regenerate with:

    java -jar synthea-with-dependencies.jar -p 40 --exporter.fhir.export true \\
         --exporter.baseDirectory ./output Massachusetts
"""

from pathlib import Path

import pytest

from memora.context.engine import compile_plan, execute_plan
from memora.context.situations import ClinicianRole, Situation
from memora.ingest.change_detector import ChangeType, apply_fact_change
from memora.ingest.pipeline import (
    MAX_EVENTS_PER_PATIENT,
    MAX_LAB_POINTS_PER_TEST,
    find_story_patients,
    ingest_patient,
    select_events,
)
from memora.ingest.synthea_parser import _text, parse_patient_bundle, slug
from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_LAB_RESULT,
    SEVERITY_CRITICAL,
    ClinicalEvent,
)
from memora.ontology.kinds import ALL_KINDS, KIND_ALLERGY, KIND_MEDICATION
from memora.sibyl.client import PatientMemory
from memora.sibyl.keys import is_safe_identifier

pytestmark = pytest.mark.integration

FHIR_DIR = Path(__file__).resolve().parents[3] / "vendor/synthea/output/fhir"


@pytest.fixture(scope="module")
def story_patients():
    if not FHIR_DIR.is_dir() or not any(FHIR_DIR.glob("*.json")):
        pytest.skip(f"no Synthea output at {FHIR_DIR}; generate it first")
    found = find_story_patients(FHIR_DIR)
    if not found:
        pytest.skip("no patient with a real drug allergy in the generated set")
    return found


@pytest.fixture(scope="module")
def parsed(story_patients):
    return parse_patient_bundle(Path(story_patients[0]["path"]))


# ---- parsing real FHIR --------------------------------------------------

def test_bundle_parses_to_ordered_events(parsed):
    patient_id, events = parsed
    assert patient_id
    assert len(events) > 50, "a real Synthea patient should be event-rich"
    stamps = [e.timestamp for e in events]
    assert stamps == sorted(stamps)
    assert all(e.timestamp for e in events), "undated events must be dropped"


def test_every_parsed_kind_is_in_the_ontology(parsed):
    """A kind the ontology does not know would be silently unretrievable."""
    _, events = parsed
    for event in events:
        if event.related_kind is not None:
            assert event.related_kind in ALL_KINDS


def test_real_drug_allergy_is_parsed_as_critical(story_patients):
    _, events = parse_patient_bundle(Path(story_patients[0]["path"]))
    drug_allergies = [e for e in events
                      if e.related_kind == KIND_ALLERGY
                      and e.severity == SEVERITY_CRITICAL]
    assert drug_allergies, "the selected patient's drug allergy was not parsed"
    assert all(e.event_type == EVENT_ADVERSE_REACTION for e in drug_allergies)
    assert "drug allergy" in drug_allergies[0].summary


def test_entity_names_from_real_drug_names_are_sibyl_safe(parsed):
    """Real medication names contain brackets, braces, slashes and commas."""
    _, events = parsed
    for event in events:
        if event.related_name:
            assert is_safe_identifier(event.related_name), event.related_name
            assert len(event.related_name) <= 60


def test_codeable_concept_falls_back_to_coding_display():
    """Observed in real bundles: .text absent, display present. Without the
    fallback those resources all collapse into one 'unknown' entity."""
    assert _text({"text": "Aspirin"}) == "Aspirin"
    assert _text({"coding": [{"display": "Penicillin V"}]}) == "Penicillin V"
    assert _text({"coding": [{"code": "1234"}]}) == "1234"
    assert _text(None, "fallback") == "fallback"
    assert _text({}, "fallback") == "fallback"


@pytest.mark.parametrize("raw", [
    "{28 (norethindrone 0.35 MG) } Pack [Jolivette]",
    "Acetaminophen 325 MG Oral Tablet [Tylenol]",
    "sodium fluoride 0.0272 MG/MG Oral Gel",
    "drug; rm -rf",
])
def test_slug_output_is_always_writable(raw):
    out = slug(raw)
    assert is_safe_identifier(out)
    assert out == out.lower()


# ---- volume selection ---------------------------------------------------

def test_labs_are_thinned_per_test(parsed):
    _, events = parsed
    selected = select_events(events)
    per_test: dict[str, int] = {}
    for event in selected:
        if event.event_type == EVENT_LAB_RESULT:
            per_test[event.related_name] = per_test.get(event.related_name, 0) + 1
    assert per_test, "expected some labs"
    assert max(per_test.values()) <= MAX_LAB_POINTS_PER_TEST


def test_selection_respects_the_per_patient_ceiling(parsed):
    _, events = parsed
    assert len(select_events(events)) <= MAX_EVENTS_PER_PATIENT


def test_critical_events_are_never_dropped_by_the_volume_cap(parsed):
    """Losing a documented drug allergy to a size limit would defeat the
    entire product."""
    _, events = parsed
    critical_before = {e.source_id for e in events if e.severity == SEVERITY_CRITICAL}
    critical_after = {e.source_id for e in select_events(events)
                      if e.severity == SEVERITY_CRITICAL}
    assert critical_before == critical_after


def test_selection_is_deterministic(parsed):
    _, events = parsed
    first = [e.source_id for e in select_events(events)]
    second = [e.source_id for e in select_events(events)]
    assert first == second


# ---- change detection against a real store ------------------------------

def test_new_then_confirmed_then_changed(store):
    memory = PatientMemory("P-CHANGE")
    event = ClinicalEvent(EVENT_LAB_RESULT, "Creatinine 1.0",
                          "2026-01-01T00:00:00Z", KIND_MEDICATION, "drug_a")

    first = apply_fact_change(memory, KIND_MEDICATION, "drug_a",
                              {"label": "Drug A", "last_seen": "2026-01-01"},
                              event, status="active")
    assert first.change is ChangeType.NEW

    # Same material content, later observation -> confirmed, not changed.
    second = apply_fact_change(memory, KIND_MEDICATION, "drug_a",
                               {"label": "Drug A", "last_seen": "2026-02-01"},
                               event, status="active")
    assert second.change is ChangeType.CONFIRMED
    assert memory.get_fact_body(KIND_MEDICATION, "drug_a")["last_seen"] == "2026-02-01"

    third = apply_fact_change(memory, KIND_MEDICATION, "drug_a",
                              {"label": "Drug A", "last_seen": "2026-03-01"},
                              event, status="discontinued")
    assert third.change is ChangeType.CHANGED
    assert third.previous_status == "active"


def test_a_change_is_journalled_before_the_row_is_overwritten(store):
    """WARM loses the old value, so the transition must already be in COLD."""
    memory = PatientMemory("P-CHANGE2")
    event = ClinicalEvent(EVENT_LAB_RESULT, "obs", "2026-01-01T00:00:00Z",
                          KIND_MEDICATION, "drug_b")
    apply_fact_change(memory, KIND_MEDICATION, "drug_b", {"label": "B"},
                      event, status="active")
    apply_fact_change(memory, KIND_MEDICATION, "drug_b", {"label": "B"},
                      event, status="discontinued")

    transitions = [h for h in memory.read_history()
                   if "status active -> discontinued" in str(h.get("acted"))]
    assert transitions, "the transition was not journalled"
    assert memory.get_fact(KIND_MEDICATION, "drug_b")["status"] == "discontinued"


# ---- full ingestion into a real store -----------------------------------

def test_real_patient_ingests_and_is_retrievable(store, story_patients):
    report = ingest_patient(Path(story_patients[0]["path"]))

    assert report.events_written > 0
    assert report.facts_new > 0
    assert report.db_size_bytes > 0
    assert report.pct_of_cap < 100, "one patient must not exhaust the free tier"

    memory = PatientMemory(report.patient_id, require_data=True)
    assert memory.list_facts(KIND_ALLERGY), "no allergies reached the store"
    assert memory.list_facts(KIND_MEDICATION)

    context = execute_plan(compile_plan(report.patient_id, Situation.ICU_TO_WARD,
                                        ClinicianRole.WARD_PHYSICIAN))
    assert not context.is_empty()
    assert context.fact_count() > 0


def test_story_patient_selection_requires_a_real_drug_allergy(story_patients):
    for candidate in story_patients:
        assert candidate["drug_allergies"]
        assert candidate["medications"] >= 3
        assert candidate["encounters"] >= 5
