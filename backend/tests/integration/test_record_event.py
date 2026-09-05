"""Recording a clinical event, and the drift it can create.

This is an ordinary write path -- adverse reactions are documented as they
happen. It matters for Sentinel because new information is exactly what makes
memory contradict itself, so this test also proves drift is DETECTED rather
than planted.
"""

import pytest
from fastapi.testclient import TestClient

from memora.context.situations import Situation
from memora.main import app
from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_MEDICATION_ADMINISTERED,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    ClinicalEvent,
)
from memora.ontology.kinds import KIND_MEDICATION, STATUS_ACTIVE
from memora.sentinel.digest import SENTINEL_SYSTEM_ID
from memora.sentinel.runner import sweep
from memora.sibyl.client import PatientMemory

pytestmark = pytest.mark.integration

PATIENT = "P-RECORD"


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def on_a_medication(store):
    """A patient whose memory is self-consistent: a medication, given once."""
    m = PatientMemory(PATIENT)
    m.set_fact(KIND_MEDICATION, "drug_a", {"label": "Drug A"}, status=STATUS_ACTIVE)
    m.log_event(ClinicalEvent(EVENT_MEDICATION_ADMINISTERED, "Drug A administered",
                              "2026-01-02T08:00:00Z", KIND_MEDICATION, "drug_a",
                              "ev-1", SEVERITY_INFO))
    return store


def _reaction():
    return {
        "event_type": EVENT_ADVERSE_REACTION,
        "summary": "Documented adverse reaction to Drug A",
        "related_kind": KIND_MEDICATION,
        "related_name": "drug_a",
        "severity": SEVERITY_CRITICAL,
    }


def test_recording_an_event_appends_to_the_journal(client, on_a_medication):
    before = PatientMemory(PATIENT).memory_version()
    r = client.post(f"/patients/{PATIENT}/events", json=_reaction())
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["event_id"]
    assert body["memory_version"] == before + 1, "a write must bump the version"
    assert body["recorded_at"]

    events = client.get(f"/patients/{PATIENT}/memory").json()["events"]
    assert any(e["event_type"] == EVENT_ADVERSE_REACTION for e in events)


def test_a_recorded_reaction_creates_real_drift(client, on_a_medication):
    """The point of this endpoint.

    Before: memory is self-consistent, Sentinel finds nothing. After a reaction
    is documented, the store says the medication is ACTIVE and also says it
    caused a reaction. Sentinel detects that contradiction on its own -- the
    finding is not planted.
    """
    assert sweep(Situation.ICU_TO_WARD, [PATIENT]).findings == []

    client.post(f"/patients/{PATIENT}/events", json=_reaction())

    run = sweep(Situation.ICU_TO_WARD, [PATIENT])
    found = [f for f in run.findings if f.name == "drug_a"]
    assert found, "Sentinel did not detect the contradiction"
    assert found[0].status == "NEW"
    assert found[0].detector == "drift"
    assert "critical_event_on_file" in found[0].triggered_rules


def test_an_unknown_event_type_is_refused(client, on_a_medication):
    r = client.post(f"/patients/{PATIENT}/events",
                    json={**_reaction(), "event_type": "vibes"})
    assert r.status_code == 422
    assert "Unknown event_type" in r.json()["detail"]


def test_an_unknown_kind_is_refused(client, on_a_medication):
    r = client.post(f"/patients/{PATIENT}/events",
                    json={**_reaction(), "related_kind": "astrology"})
    assert r.status_code == 422


def test_recording_is_503_without_the_memory_layer(client, on_a_medication):
    on_a_medication.unlink()
    r = client.post(f"/patients/{PATIENT}/events", json=_reaction())
    assert r.status_code == 503
    assert r.json()["error"] == "sibyl_unavailable"


def test_cannot_record_against_an_unknown_patient(client, on_a_medication):
    r = client.post("/patients/P-NOBODY/events", json=_reaction())
    assert r.status_code == 404


def test_cannot_record_against_the_sentinel_tenant(client, on_a_medication):
    r = client.post(f"/patients/{SENTINEL_SYSTEM_ID}/events", json=_reaction())
    assert r.status_code == 404


def test_a_supplied_timestamp_is_honoured(client, on_a_medication):
    r = client.post(f"/patients/{PATIENT}/events",
                    json={**_reaction(), "timestamp": "2026-03-15T09:00:00Z"})
    assert r.json()["recorded_at"] == "2026-03-15T09:00:00Z"
