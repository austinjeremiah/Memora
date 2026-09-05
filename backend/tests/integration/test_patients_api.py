"""Patient discovery and the raw-memory view.

These exist because the frontend previously had no way to learn who was in
the store and shipped a hardcoded fixture id. Real ids are Synthea UUIDs
generated per ingestion run -- they cannot be known ahead of time.
"""

import pytest
from fastapi.testclient import TestClient

from memora.main import app
from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_LAB_RESULT,
    SEVERITY_CRITICAL,
    ClinicalEvent,
)
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_LAB_TREND,
    KIND_MEDICATION,
    STATUS_ACTIVE,
    STATUS_DOCUMENTED,
)
from memora.sentinel.digest import SENTINEL_SYSTEM_ID
from memora.sibyl.client import PatientMemory

pytestmark = pytest.mark.integration

PATIENT = "P-DISCOVER"


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def populated(store):
    m = PatientMemory(PATIENT)
    m.set_fact(KIND_MEDICATION, "drug_a", {"label": "Drug A"}, status=STATUS_ACTIVE)
    m.set_fact(KIND_ALLERGY, "penicillin_v",
               {"allergen": "Penicillin V", "is_drug_allergy": True,
                "criticality": "low"}, status=STATUS_DOCUMENTED)
    m.set_fact(KIND_LAB_TREND, "creatinine", {
        "test": "Creatinine", "loinc": "2160-0", "unit": "mg/dL",
        "readings": 3, "direction": "rising", "delta": 0.6,
        "latest_value": 1.9, "latest_at": "2026-03-01",
        "series": [{"value": 1.3, "at": "2026-01-01"},
                   {"value": 1.6, "at": "2026-02-01"},
                   {"value": 1.9, "at": "2026-03-01"}],
    }, status=STATUS_ACTIVE)
    m.set_fact(KIND_LAB_TREND, "sodium", {
        "test": "Sodium", "loinc": "2951-2", "unit": "mmol/L",
        "readings": 1, "direction": "single_reading", "delta": None,
        "latest_value": 138, "latest_at": "2026-03-01",
        "series": [{"value": 138, "at": "2026-03-01"}],
    }, status=STATUS_ACTIVE)
    m.log_event(ClinicalEvent(EVENT_ADVERSE_REACTION, "Reaction to Penicillin",
                              "2026-01-04T00:00:00Z", KIND_ALLERGY,
                              "penicillin_v", "ev-1", SEVERITY_CRITICAL))
    m.log_event(ClinicalEvent(EVENT_LAB_RESULT, "Creatinine 1.9",
                              "2026-03-01T00:00:00Z", KIND_LAB_TREND,
                              "creatinine", "ev-2"))
    return store


# ---- GET /patients ------------------------------------------------------

def test_patients_are_discoverable_not_hardcoded(client, populated):
    r = client.get("/patients")
    assert r.status_code == 200
    ids = [p["patient_id"] for p in r.json()]
    assert PATIENT in ids


def test_patient_summary_is_informative_enough_to_choose_from(client, populated):
    row = next(p for p in client.get("/patients").json()
               if p["patient_id"] == PATIENT)
    assert row["fact_count"] == 4
    assert row["event_count"] == 2
    assert row["memory_version"] == 2      # one per journal write
    assert row["has_drug_allergy"] is True
    assert row["kinds"][KIND_LAB_TREND] == 2
    assert row["last_updated"]


def test_the_sentinel_pseudo_tenant_is_never_listed_as_a_patient(client, populated):
    """It holds Sentinel's digest, not clinical data."""
    from memora.context.situations import Situation
    from memora.sentinel.runner import sweep
    sweep(Situation.ICU_TO_WARD, [PATIENT])   # forces a digest write

    ids = [p["patient_id"] for p in client.get("/patients").json()]
    assert SENTINEL_SYSTEM_ID not in ids


def test_patients_is_503_without_the_memory_layer(client, populated):
    populated.unlink()
    r = client.get("/patients")
    assert r.status_code == 503
    assert r.json()["error"] == "sibyl_unavailable"


# ---- GET /patients/{id}/memory ------------------------------------------

def test_memory_view_returns_the_raw_record(client, populated):
    r = client.get(f"/patients/{PATIENT}/memory")
    assert r.status_code == 200
    body = r.json()
    assert body["fact_count"] == 4
    assert body["event_count"] == 2
    assert set(body["facts"]) == {KIND_MEDICATION, KIND_ALLERGY, KIND_LAB_TREND}
    assert body["memory"]["soft_cap_bytes"] == 5_242_880


def test_memory_view_is_unfiltered_unlike_context(client, populated):
    """/context returns one situation's ranked, capped plan. This returns
    everything -- that difference is the whole reason it exists."""
    memory = client.get(f"/patients/{PATIENT}/memory").json()
    context = client.get(f"/patients/{PATIENT}/context",
                         params={"situation": "pre_operative",
                                 "clinician_id": "dr_priya"}).json()
    memory_kinds = set(memory["facts"])
    context_kinds = {f["kind"] for f in context["facts"]}
    assert KIND_LAB_TREND in memory_kinds
    assert KIND_LAB_TREND not in context_kinds


def test_trends_carry_their_full_series_and_rank_first(client, populated):
    trends = client.get(f"/patients/{PATIENT}/memory").json()["trends"]
    assert [t["name"] for t in trends] == ["creatinine", "sodium"], \
        "multi-reading trajectories must rank above single readings"
    creatinine = trends[0]
    assert creatinine["loinc"] == "2160-0"
    assert creatinine["direction"] == "rising"
    assert len(creatinine["series"]) == 3
    assert [p["value"] for p in creatinine["series"]] == [1.3, 1.6, 1.9]


def test_events_are_newest_first_with_provenance(client, populated):
    events = client.get(f"/patients/{PATIENT}/memory").json()["events"]
    stamps = [e["timestamp"] for e in events]
    assert stamps == sorted(stamps, reverse=True)
    critical = next(e for e in events if e["severity"] == SEVERITY_CRITICAL)
    assert critical["source_id"] == "ev-1"
    assert critical["related_name"] == "penicillin_v"


def test_event_limit_is_respected(client, populated):
    body = client.get(f"/patients/{PATIENT}/memory",
                      params={"event_limit": 1}).json()
    assert len(body["events"]) == 1


def test_memory_view_is_404_for_the_reserved_tenant(client, populated):
    assert client.get(f"/patients/{SENTINEL_SYSTEM_ID}/memory").status_code == 404


def test_memory_view_is_404_for_an_unknown_patient(client, populated):
    assert client.get("/patients/P-NOBODY/memory").status_code == 404


def test_memory_view_is_503_without_the_memory_layer(client, populated):
    populated.unlink()
    r = client.get(f"/patients/{PATIENT}/memory")
    assert r.status_code == 503
    assert r.json()["error"] == "sibyl_unavailable"
