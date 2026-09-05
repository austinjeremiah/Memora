"""Answering a clinician's question from memory.

Retrieval here is question-driven via Sibyl's FTS5 index rather than
situation-driven. Everything after retrieval is unchanged -- the model
proposes, the resolver checks, the gate decides -- so a question earns the
model no extra latitude.
"""

import pytest
from fastapi.testclient import TestClient

from memora.llm.answer import extract_terms, search_memory
from memora.main import app
from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    SEVERITY_CRITICAL,
    ClinicalEvent,
)
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_MEDICATION,
    STATUS_ACTIVE,
    STATUS_CONTRAINDICATED,
    STATUS_DOCUMENTED,
)
from memora.sibyl.client import PatientMemory

pytestmark = pytest.mark.integration

PATIENT = "P-ASK"


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def seeded(store):
    m = PatientMemory(PATIENT)
    m.set_fact(KIND_MEDICATION, "warfarin", {"label": "Warfarin 5mg"},
               status=STATUS_CONTRAINDICATED)
    m.set_fact(KIND_MEDICATION, "paracetamol", {"label": "Paracetamol 500mg"},
               status=STATUS_ACTIVE)
    m.set_fact(KIND_ALLERGY, "penicillin", {"allergen": "Penicillin V",
                                            "is_drug_allergy": True},
               status=STATUS_DOCUMENTED)
    m.log_event(ClinicalEvent(EVENT_ADVERSE_REACTION, "Adverse reaction to warfarin",
                              "2026-02-01T00:00:00Z", KIND_MEDICATION, "warfarin",
                              "ev-warf", SEVERITY_CRITICAL))
    return store


# ---- term extraction ----------------------------------------------------

def test_stopwords_are_dropped():
    """A query of only stopwords matches everything and therefore nothing."""
    assert extract_terms("Is it safe?") == []
    assert "warfarin" in extract_terms("Can I restart the warfarin?")
    assert "the" not in extract_terms("Can I restart the warfarin?")


def test_terms_are_bounded():
    long_q = " ".join(f"term{i}" for i in range(40))
    assert len(extract_terms(long_q)) <= 8


# ---- FTS retrieval ------------------------------------------------------

def test_a_question_finds_the_record_it_names(seeded):
    ctx = search_memory(PatientMemory(PATIENT), "Can I restart warfarin?")
    names = [m["name"] for m in ctx.matches]
    assert "warfarin" in names


def test_matched_records_bring_their_history(seeded):
    ctx = search_memory(PatientMemory(PATIENT), "warfarin")
    assert any(e.event_type == EVENT_ADVERSE_REACTION for e in ctx.events)


def test_a_question_about_nothing_matches_nothing(seeded):
    ctx = search_memory(PatientMemory(PATIENT), "amiodarone dosing")
    assert ctx.is_empty()


# ---- the endpoint -------------------------------------------------------

def test_unanswerable_questions_do_not_reach_the_model(client, seeded):
    """The important one. With no matches the model is never asked -- inviting
    it to answer from an empty result set is how fabrication happens."""
    r = client.post(f"/patients/{PATIENT}/ask",
                    json={"question": "What is the amiodarone plan?",
                          "clinician_id": "dr_maya"})
    assert r.status_code == 200
    body = r.json()
    assert body["answered"] is False
    assert body["answer"] == ""
    assert body["claims"] == []
    assert body["matched"] == []


def test_ask_requires_a_known_clinician(client, seeded):
    r = client.post(f"/patients/{PATIENT}/ask",
                    json={"question": "warfarin?", "clinician_id": "dr_who"})
    assert r.status_code == 400


def test_ask_is_503_without_the_memory_layer(client, seeded):
    seeded.unlink()
    r = client.post(f"/patients/{PATIENT}/ask",
                    json={"question": "warfarin?", "clinician_id": "dr_maya"})
    assert r.status_code == 503
    assert r.json()["error"] == "sibyl_unavailable"


def test_ask_rejects_the_reserved_tenant(client, seeded):
    from memora.sentinel.digest import SENTINEL_SYSTEM_ID
    r = client.post(f"/patients/{SENTINEL_SYSTEM_ID}/ask",
                    json={"question": "anything", "clinician_id": "dr_maya"})
    assert r.status_code == 404


def test_a_too_short_question_is_refused(client, seeded):
    r = client.post(f"/patients/{PATIENT}/ask",
                    json={"question": "x", "clinician_id": "dr_maya"})
    assert r.status_code == 422


@pytest.mark.llm
def test_a_real_question_is_answered_from_the_record(client, seeded):
    r = client.post(f"/patients/{PATIENT}/ask",
                    json={"question": "Can I restart warfarin?",
                          "clinician_id": "dr_maya"})
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["matched"], "FTS found nothing for a record that exists"
    assert "warfarin" in body["search_terms"]

    # However the model phrases it, nothing may be presented without evidence.
    for claim in body["claims"]:
        if claim["gate_result"] != "BLOCK":
            assert claim["source_kind"] and claim["source_name"]

    # Warfarin is contraindicated with a critical event on file -- if the model
    # cited it at all, the gate must not have waved it through.
    for claim in body["claims"]:
        if claim["source_name"] == "warfarin" and claim["gate_result"] != "BLOCK":
            assert claim["gate_result"] == "NEEDS_REVIEW"


@pytest.mark.llm
def test_an_answer_with_every_claim_blocked_is_not_presented(client, seeded):
    """Prose whose supporting claims were all refused is a refusal, not an
    answer. `answered` gates the whole response."""
    body = client.post(f"/patients/{PATIENT}/ask",
                       json={"question": "penicillin allergy",
                             "clinician_id": "dr_maya"}).json()
    if body["claims"] and all(c["gate_result"] == "BLOCK" for c in body["claims"]):
        assert body["answered"] is False
        assert body["answer"] == ""
