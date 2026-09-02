"""HTTP surface, exercised through the real ASGI app.

TestClient runs the actual application -- real routing, real handlers, real
exception mapping, real Sibyl store underneath. Nothing is stubbed.
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
    KIND_PROCEDURE,
    STATUS_ACTIVE,
    STATUS_CONTRAINDICATED,
    STATUS_DOCUMENTED,
)
from memora.sibyl.client import PatientMemory

PATIENT = "P-10482"


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def seeded(store):
    m = PatientMemory(PATIENT)
    m.set_fact(KIND_MEDICATION, "drug_a", {"reason": "adverse reaction"},
               status=STATUS_CONTRAINDICATED)
    m.set_fact(KIND_MEDICATION, "drug_b", {"dose": "5mg"}, status=STATUS_ACTIVE)
    m.set_fact(KIND_ALLERGY, "penicillin", {"reaction": "anaphylaxis"},
               status=STATUS_DOCUMENTED)
    m.set_fact(KIND_LAB_TREND, "creatinine", {"trend": "rising"}, status=STATUS_ACTIVE)
    m.set_fact(KIND_PROCEDURE, "central_line", {"site": "right IJ"}, status="performed")
    m.log_event(ClinicalEvent(EVENT_ADVERSE_REACTION, "Reaction to Drug A",
                              "2026-01-04T14:30:00Z", KIND_MEDICATION, "drug_a",
                              "ev-1", SEVERITY_CRITICAL))
    m.log_event(ClinicalEvent(EVENT_LAB_RESULT, "Creatinine 2.1 rising",
                              "2026-01-05T06:00:00Z", KIND_LAB_TREND, "creatinine",
                              "ev-2"))
    return store


# ---- basics -------------------------------------------------------------

def test_health_is_liveness_only(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readyz_reports_sibyl_reachable(client, store):
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["sibyl"] is True


def test_readyz_is_503_when_memory_layer_is_gone(client, store):
    store.unlink()
    r = client.get("/readyz")
    assert r.status_code == 503
    assert r.json()["detail"]["sibyl"] is False


def test_clinicians_are_listed_with_their_rights(client):
    r = client.get("/clinicians")
    assert r.status_code == 200
    by_id = {c["id"]: c for c in r.json()}
    assert by_id["dr_priya"]["can_approve_handoff"] is False
    assert by_id["dr_maya"]["role"] == "icu_physician"


# ---- situational recall over HTTP, no model involved --------------------

def test_context_returns_situational_subset(client, seeded):
    r = client.get(f"/patients/{PATIENT}/context",
                   params={"situation": "icu_to_ward", "clinician_id": "dr_maya"})
    assert r.status_code == 200
    body = r.json()
    assert body["task"] == "medication_reconciliation"
    kinds = {f["kind"] for f in body["facts"]}
    assert KIND_LAB_TREND in kinds
    assert KIND_PROCEDURE not in kinds
    assert body["memory"]["soft_cap_bytes"] == 5_242_880


def test_same_patient_different_situation_differs_over_http(client, seeded):
    icu = client.get(f"/patients/{PATIENT}/context",
                     params={"situation": "icu_to_ward", "clinician_id": "dr_maya"}).json()
    preop = client.get(f"/patients/{PATIENT}/context",
                       params={"situation": "pre_operative",
                               "clinician_id": "dr_priya"}).json()
    assert {f["kind"] for f in icu["facts"]} != {f["kind"] for f in preop["facts"]}
    assert KIND_PROCEDURE in {f["kind"] for f in preop["facts"]}


def test_context_carries_provenance_fields(client, seeded):
    body = client.get(f"/patients/{PATIENT}/context",
                      params={"situation": "icu_to_ward",
                              "clinician_id": "dr_maya"}).json()
    drug_a = next(f for f in body["facts"] if f["name"] == "drug_a")
    assert drug_a["status"] == STATUS_CONTRAINDICATED
    assert any(e["severity"] == SEVERITY_CRITICAL for e in body["history"])


# ---- honest failure mapping ---------------------------------------------

def test_context_is_503_when_memory_layer_is_deleted(client, seeded):
    """The deletion test at the HTTP boundary: a refusal, never an empty 200."""
    seeded.unlink()
    r = client.get(f"/patients/{PATIENT}/context",
                   params={"situation": "icu_to_ward", "clinician_id": "dr_maya"})
    assert r.status_code == 503
    assert r.json()["error"] == "sibyl_unavailable"


def test_unknown_patient_is_404_not_503(client, seeded):
    """A healthy store with no data for this patient is a different condition
    from the memory layer being gone."""
    r = client.get("/patients/P-NOBODY/context",
                   params={"situation": "icu_to_ward", "clinician_id": "dr_maya"})
    assert r.status_code == 404
    assert r.json()["error"] == "patient_unknown"


def test_unknown_clinician_is_400(client, seeded):
    r = client.get(f"/patients/{PATIENT}/context",
                   params={"situation": "icu_to_ward", "clinician_id": "dr_who"})
    assert r.status_code == 400


def test_unknown_situation_is_422(client, seeded):
    r = client.get(f"/patients/{PATIENT}/context",
                   params={"situation": "tea_break", "clinician_id": "dr_maya"})
    assert r.status_code == 422


def test_handoff_rejects_invalid_situation_at_the_schema(client, seeded):
    r = client.post("/handoff", json={"patient_id": PATIENT, "situation": "tea_break",
                                      "clinician_id": "dr_maya"})
    assert r.status_code == 422


def test_handoff_is_503_when_memory_layer_is_deleted(client, seeded):
    """The single most important HTTP behaviour in the service."""
    seeded.unlink()
    r = client.post("/handoff", json={"patient_id": PATIENT,
                                      "situation": "icu_to_ward",
                                      "clinician_id": "dr_maya"})
    assert r.status_code == 503
    assert r.json()["error"] == "sibyl_unavailable"
    assert "claims" not in r.json()


# ---- the full pipeline over HTTP ----------------------------------------

@pytest.mark.llm
def test_handoff_runs_the_full_pipeline(client, seeded):
    r = client.post("/handoff", json={"patient_id": PATIENT,
                                      "situation": "icu_to_ward",
                                      "clinician_id": "dr_maya"})
    assert r.status_code == 200
    body = r.json()
    assert body["proposed_count"] >= 1
    assert body["claims"]
    assert sum(body["summary"].values()) == len(body["claims"])

    for claim in body["claims"]:
        assert claim["gate_result"] in {"ALLOW", "NEEDS_REVIEW", "BLOCK"}
        if claim["gate_result"] != "BLOCK":
            assert claim["source_kind"], "a presented claim carried no source"


@pytest.mark.llm
def test_handoff_flags_the_contraindicated_medication(client, seeded):
    body = client.post("/handoff", json={"patient_id": PATIENT,
                                         "situation": "icu_to_ward",
                                         "clinician_id": "dr_maya"}).json()
    for claim in body["claims"]:
        if claim["source_name"] == "drug_a" and claim["gate_result"] != "BLOCK":
            assert claim["gate_result"] == "NEEDS_REVIEW"
            assert "contraindicated_record" in claim["triggered_rules"]
            assert claim["source_events"], "flagged claim carried no cited events"
