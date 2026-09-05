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

    body = client.post(f"/patients/{PATIENT}/events", json=_reaction()).json()

    # The agent checks during the write, so IT sees the contradiction first.
    autonomous = [f for f in body["autonomous_check"]["findings"]
                  if f["name"] == "drug_a"]
    assert autonomous, "the agent did not notice the contradiction it received"
    assert autonomous[0]["status"] == "NEW"
    assert autonomous[0]["detector"] == "drift"
    assert "critical_event_on_file" in autonomous[0]["triggered_rules"]

    # A human sweeping afterwards correctly finds it already known -- announced
    # once, then tracked. Reporting NEW again would be the alert fatigue the
    # state machine exists to prevent.
    run = sweep(Situation.ICU_TO_WARD, [PATIENT])
    found = [f for f in run.findings if f.name == "drug_a"]
    assert found and found[0].status == "PERSISTING"


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


# ---- the agent acting on its own ----------------------------------------

def test_recording_an_event_triggers_an_unprompted_check(client, on_a_medication):
    """Nobody asked for this. New information entering memory is the trigger,
    which is what makes it the agent acting rather than a feature invoked."""
    body = client.post(f"/patients/{PATIENT}/events", json=_reaction()).json()

    check = body["autonomous_check"]
    assert check is not None
    assert check["ran"] is True
    assert check["records_checked"] > 0
    assert any(f["name"] == "drug_a" for f in check["findings"]), \
        "the agent did not notice the contradiction it just received"


def test_a_self_consistent_event_triggers_a_check_that_finds_nothing(client,
                                                                     on_a_medication):
    """The check runs regardless; finding nothing is a valid outcome."""
    body = client.post(f"/patients/{PATIENT}/events", json={
        "event_type": EVENT_MEDICATION_ADMINISTERED,
        "summary": "Drug A administered again",
        "related_kind": KIND_MEDICATION, "related_name": "drug_a",
        "severity": SEVERITY_INFO,
    }).json()
    assert body["autonomous_check"]["ran"] is True
    assert body["autonomous_check"]["findings"] == []


def test_the_event_survives_a_failing_autonomous_check(client, on_a_medication,
                                                       monkeypatch):
    """A degraded agent must not cost a clinical record. The write stands."""
    from memora.api import routes

    def explode(*_a, **_k):
        raise RuntimeError("sweep is broken")

    monkeypatch.setattr(routes, "sweep", explode)
    r = client.post(f"/patients/{PATIENT}/events", json=_reaction())
    assert r.status_code == 200
    assert r.json()["event_id"], "the event was lost when the check failed"
    assert r.json()["autonomous_check"]["ran"] is False

    events = client.get(f"/patients/{PATIENT}/memory").json()["events"]
    assert any(e["event_type"] == EVENT_ADVERSE_REACTION for e in events)


# ---- escalation: memory changing what the agent DOES ---------------------

def test_escalation_writes_into_the_patient_record(client, on_a_medication):
    """The trigger exists ONLY in Sentinel's own memory.

    `runs_seen` comes from the digest. Without that persisted count there is no
    threshold to cross, so this action is unreachable without memory -- which
    is the eligibility gate stated precisely.
    """
    from memora.context.situations import Situation
    from memora.sentinel.runner import sweep

    client.post(f"/patients/{PATIENT}/events", json=_reaction())

    # Sweep until the finding crosses the escalation threshold. The action
    # fires on the run that crosses it and is deliberately not repeated, so
    # collect across runs rather than inspecting the last one.
    actions = []
    for _ in range(4):
        actions += sweep(Situation.ICU_TO_WARD, [PATIENT],
                         escalation_threshold=3).actions_taken

    assert actions, "the agent escalated nothing"
    action = actions[0]
    assert action["action"] == "escalated_to_patient_record"
    assert action["runs_seen"] >= 3

    # And it is in the patient's own journal, where a clinician would see it.
    events = client.get(f"/patients/{PATIENT}/memory").json()["events"]
    flagged = [e for e in events if "Flagged for review by Sentinel" in e["summary"]]
    assert flagged, "the escalation never reached the record"
    assert flagged[0]["severity"] == SEVERITY_CRITICAL
    assert flagged[0]["source_id"].startswith("sentinel-escalation")


def test_escalation_is_written_only_once(client, on_a_medication):
    """An agent that repeats itself is noise, and this record is the thing
    being protected."""
    from memora.context.situations import Situation
    from memora.sentinel.runner import sweep

    client.post(f"/patients/{PATIENT}/events", json=_reaction())
    for _ in range(6):
        sweep(Situation.ICU_TO_WARD, [PATIENT], escalation_threshold=3)

    events = client.get(f"/patients/{PATIENT}/memory").json()["events"]
    flagged = [e for e in events if "Flagged for review by Sentinel" in e["summary"]]
    assert len(flagged) == 1, f"escalated {len(flagged)} times, expected once"
