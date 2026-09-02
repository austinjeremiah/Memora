"""Repository layer against a real Sibyl store -- all five tiers."""

import pytest

from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_MEDICATION_DISCONTINUED,
    SEVERITY_CRITICAL,
    ClinicalEvent,
)
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_MEDICATION,
    STATUS_ACTIVE,
    STATUS_CONTRAINDICATED,
)
from memora.sibyl.client import PatientMemory

pytestmark = pytest.mark.integration


def test_warm_fact_roundtrip_returns_row_with_body_and_status(store):
    m = PatientMemory("P-10482")
    m.set_fact(KIND_MEDICATION, "drug_a", {"note": "started on admission"}, status=STATUS_ACTIVE)

    row = m.get_fact(KIND_MEDICATION, "drug_a")
    assert row["category"] == KIND_MEDICATION
    assert row["name"] == "drug_a"
    # The clinical payload is nested under "body" -- reading status off the row
    # and the body are different things, and both must work as documented.
    assert row["body"]["note"] == "started on admission"
    assert row["status"] == STATUS_ACTIVE
    assert m.get_fact_body(KIND_MEDICATION, "drug_a") == {"note": "started on admission"}


def test_missing_fact_returns_none_not_raises(store):
    m = PatientMemory("P-10482")
    assert m.get_fact(KIND_MEDICATION, "never_written") is None
    assert m.get_fact_body(KIND_MEDICATION, "never_written") is None


def test_status_is_a_real_queryable_column(store):
    m = PatientMemory("P-10482")
    m.set_fact(KIND_MEDICATION, "drug_a", {"n": 1}, status=STATUS_CONTRAINDICATED)
    m.set_fact(KIND_MEDICATION, "drug_b", {"n": 2}, status=STATUS_ACTIVE)

    flagged = m.list_facts(KIND_MEDICATION, status=STATUS_CONTRAINDICATED)
    assert [r["name"] for r in flagged] == ["drug_a"]
    assert len(m.list_facts(KIND_MEDICATION)) == 2


def test_list_facts_enumerates_completely(store):
    m = PatientMemory("P-10482")
    for i in range(12):
        m.set_fact(KIND_MEDICATION, f"drug_{i}", {"n": i}, status=STATUS_ACTIVE)
    assert len(m.list_facts(KIND_MEDICATION)) == 12


def test_cold_event_roundtrip_preserves_structure_and_time(store):
    m = PatientMemory("P-10482")
    event = ClinicalEvent(
        event_type=EVENT_ADVERSE_REACTION,
        summary="Documented reaction to Drug A",
        timestamp="2026-01-05T10:00:00Z",
        related_kind=KIND_MEDICATION,
        related_name="drug_a",
        source_id="fhir-abc-123",
        severity=SEVERITY_CRITICAL,
    )
    m.log_event(event)

    history = m.read_history()
    assert len(history) == 1
    rebuilt = ClinicalEvent.from_record(history[0])
    assert rebuilt.event_type == EVENT_ADVERSE_REACTION
    assert rebuilt.summary == "Documented reaction to Drug A"
    assert rebuilt.source_id == "fhir-abc-123"
    assert rebuilt.severity == SEVERITY_CRITICAL
    assert rebuilt.related_name == "drug_a"
    # The clinical timestamp, not the ingestion wall clock.
    assert history[0]["ts"].startswith("2026-01-05")


def test_read_history_is_not_silently_truncated_at_fifty(store):
    """The SDK's own default limit is 50. Older history must stay reachable,
    or the Evidence Resolver would reject true claims for lack of a source."""
    m = PatientMemory("P-10482")
    for i in range(60):
        m.log_event(ClinicalEvent(
            event_type=EVENT_MEDICATION_DISCONTINUED,
            summary=f"event {i}",
            timestamp=f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
        ))
    assert len(m.read_history()) == 60


def test_hot_state_roundtrip_unwraps_body(store):
    m = PatientMemory("P-10482")
    m.set_context("active_situation", {"situation": "icu_to_ward", "role": "ward_physician"})
    assert m.get_context("active_situation") == {
        "situation": "icu_to_ward", "role": "ward_physician",
    }
    assert m.get_context("never_set") is None


def test_reference_roundtrip_decodes_json_body(store):
    m = PatientMemory("P-10482")
    m.set_reference("clinical_policy", {"rule": "flag adverse reactions"})
    ref = m.get_reference("clinical_policy")
    assert ref["body"] == {"rule": "flag adverse reactions"}
    assert m.get_reference("never_set") is None


def test_archive_retires_without_hard_delete(store):
    m = PatientMemory("P-10482")
    m.set_fact(KIND_ALLERGY, "penicillin", {"reaction": "anaphylaxis"}, status="documented")
    size_before = store.stat().st_size

    m.archive_fact(KIND_ALLERGY, "penicillin", reason="superseded")

    assert m.get_fact(KIND_ALLERGY, "penicillin") is None
    assert not any(h["name"] == "penicillin" for h in m.search("penicillin"))
    assert store.stat().st_size >= size_before  # archived on disk, not shrunk away


def test_search_is_tenant_scoped_and_kind_filterable(store):
    m = PatientMemory("P-10482")
    m.set_fact(KIND_MEDICATION, "amoxicillin", {"n": 1}, status=STATUS_ACTIVE)
    m.set_fact(KIND_ALLERGY, "amoxicillin_rash", {"n": 2}, status="documented")

    assert len(m.search("amoxicillin")) == 2
    meds = m.search("amoxicillin", kind=KIND_MEDICATION)
    assert [h["name"] for h in meds] == ["amoxicillin"]


def test_quota_reports_the_real_five_megabyte_cap(store):
    m = PatientMemory("P-10482")
    q = m.quota()
    assert q["soft_cap_bytes"] == 5_242_880
    assert q["at_or_above_cap"] is False
