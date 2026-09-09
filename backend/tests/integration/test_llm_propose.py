"""LLM proposal layer.

Tests marked `llm` make REAL calls to the configured provider. Nothing here is
mocked: the point of this layer is how an actual model behaves against actual
retrieved memory, and a fake response would test only my own assumptions about
it. Deselect with `-m "not llm"` if you are rate limited.
"""

import pytest

from memora.clinicians.roles import get_clinician
from memora.config import settings
from memora.context.engine import compile_plan, execute_plan
from memora.context.situations import ClinicianRole, Situation
from memora.evidence.resolver import RejectionReason, resolve_all
from memora.gate.gate import GateResult, evaluate_all
from memora.llm import client as llm_client
from memora.llm.client import get_client
from memora.llm.errors import LLMUnavailableError
from memora.llm.propose import SYSTEM_PROMPT, build_payload, propose_claims
from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_MEDICATION_DISCONTINUED,
    SEVERITY_CRITICAL,
    ClinicalEvent,
)
from memora.ontology.kinds import (
    ALL_KINDS,
    KIND_ALLERGY,
    KIND_MEDICATION,
    STATUS_ACTIVE,
    STATUS_CONTRAINDICATED,
    STATUS_DOCUMENTED,
)
from memora.sibyl.client import PatientMemory

PATIENT = "P-10482"


@pytest.fixture
def context(store):
    m = PatientMemory(PATIENT)
    m.set_fact(KIND_MEDICATION, "drug_a", {"reason": "adverse reaction"},
               status=STATUS_CONTRAINDICATED)
    m.set_fact(KIND_MEDICATION, "drug_b", {"dose": "5mg BD"}, status=STATUS_ACTIVE)
    m.set_fact(KIND_ALLERGY, "penicillin", {"reaction": "anaphylaxis"},
               status=STATUS_DOCUMENTED)
    m.log_event(ClinicalEvent(EVENT_ADVERSE_REACTION, "Adverse reaction to Drug A",
                              "2026-01-04T14:30:00Z", KIND_MEDICATION, "drug_a",
                              "ev-1", SEVERITY_CRITICAL))
    m.log_event(ClinicalEvent(EVENT_MEDICATION_DISCONTINUED, "Drug A discontinued",
                              "2026-01-04T16:00:00Z", KIND_MEDICATION, "drug_a", "ev-2"))
    return execute_plan(compile_plan(PATIENT, Situation.ICU_TO_WARD,
                                     ClinicianRole.WARD_PHYSICIAN))


# ---- payload construction (no network) ----------------------------------

def test_payload_lists_exact_citable_pairs(context):
    payload = build_payload(context)
    pairs = {(c["related_kind"], c["related_name"]) for c in payload["citable_records"]}
    assert (KIND_MEDICATION, "drug_a") in pairs
    assert (KIND_ALLERGY, "penicillin") in pairs
    assert payload["situation"] == "icu_to_ward"
    assert payload["clinical_task"] == "medication_reconciliation"


def test_payload_carries_status_and_severity(context):
    payload = build_payload(context)
    drug_a = next(f for f in payload["current_facts"] if f["related_name"] == "drug_a")
    assert drug_a["status"] == STATUS_CONTRAINDICATED
    assert any(h["severity"] == SEVERITY_CRITICAL for h in payload["history"])


def test_prompt_pins_the_closed_kind_vocabulary():
    """The model invented kinds on its first live call, so every valid kind
    must appear in the prompt verbatim."""
    for kind in ALL_KINDS:
        assert kind in SYSTEM_PROMPT


def test_empty_retrieval_proposes_nothing_without_calling_the_model(store):
    """Asking a model to summarise an empty record set invites invention."""
    PatientMemory(PATIENT).set_fact(KIND_MEDICATION, "seed", {"n": 1},
                                    status=STATUS_ACTIVE)
    ctx = execute_plan(compile_plan(PATIENT, Situation.PRE_OPERATIVE,
                                    ClinicianRole.SURGEON))
    ctx.facts, ctx.history = {}, []
    assert propose_claims(ctx) == []


def test_missing_api_key_is_loud_not_silent(monkeypatch):
    """No key at all must raise rather than quietly skip the proposal step.

    Both settings are cleared: LLM_API_KEYS feeds the same pool, so leaving a
    rotation key configured would (correctly) keep the client usable and this
    test would be asserting nothing.
    """
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_api_keys", [])
    llm_client._pool.cache_clear()
    with pytest.raises(LLMUnavailableError):
        get_client()
    llm_client._pool.cache_clear()


def test_every_configured_key_joins_the_pool(monkeypatch):
    """LLM_API_KEYS adds to LLM_API_KEY rather than replacing it."""
    monkeypatch.setattr(settings, "llm_api_key", "gsk_primary")
    monkeypatch.setattr(settings, "llm_api_keys", ["gsk_second", "gsk_primary"])
    llm_client._pool.cache_clear()
    try:
        # The duplicate is dropped; the primary still leads.
        assert llm_client.key_count() == 2
        seen = {llm_client.get_client().api_key for _ in range(4)}
        assert seen == {"gsk_primary", "gsk_second"}
    finally:
        llm_client._pool.cache_clear()


# ---- live model calls ---------------------------------------------------

@pytest.mark.llm
def test_model_proposes_claims_citing_real_records(context):
    claims = propose_claims(context)
    assert claims, "model proposed nothing from a populated context"
    for claim in claims:
        assert isinstance(claim, dict)
        assert claim.get("text")


@pytest.mark.llm
def test_whatever_the_model_proposes_is_verified_not_trusted(context, store):
    """The load-bearing guarantee: real model output, checked against memory.

    This does not assert the model behaves. It asserts that however it behaves,
    nothing reaches ALLOW without a record backing it.
    """
    memory = PatientMemory(PATIENT)
    claims = propose_claims(context)
    checks = resolve_all(memory, claims)
    decisions = evaluate_all(memory, checks, get_clinician("dr_arun").role)

    for check, decision in zip(checks, decisions, strict=True):
        if decision.result is not GateResult.BLOCK:
            assert check.supported, "a claim passed the gate without evidence"
            assert check.source_kind in ALL_KINDS
            assert check.has_current_fact or check.source_events

    # The contraindicated drug must never come back as a clean ALLOW.
    for check, decision in zip(checks, decisions, strict=True):
        if check.source_name == "drug_a" and check.supported:
            assert decision.result is GateResult.NEEDS_REVIEW


@pytest.mark.llm
def test_invented_kinds_are_caught_when_the_model_emits_them(context):
    """The model returned related_kind="adverse_reaction" and "event" on first
    contact. If it does so again, the resolver must reject it rather than the
    prompt being the only defence."""
    memory = PatientMemory(PATIENT)
    claims = propose_claims(context)
    checks = resolve_all(memory, claims)

    for claim, check in zip(claims, checks, strict=True):
        kind = claim.get("related_kind") if isinstance(claim, dict) else None
        if kind is not None and kind not in ALL_KINDS:
            assert check.rejection is RejectionReason.UNKNOWN_KIND
            assert check.supported is False
