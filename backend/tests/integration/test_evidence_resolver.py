"""Evidence Resolver against a real Sibyl store.

The rule under test: a claim is supported only if a record actually exists.
Nothing here consults a model, and fluent prose earns nothing on its own.
"""

import pytest

from memora.evidence.resolver import (
    RejectionReason,
    resolve_all,
    resolve_claim,
)
from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_MEDICATION_ADMINISTERED,
    EVENT_MEDICATION_DISCONTINUED,
    SEVERITY_CRITICAL,
    ClinicalEvent,
)
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_MEDICATION,
    STATUS_CONTRAINDICATED,
)
from memora.sibyl.client import PatientMemory
from memora.sibyl.errors import SibylUnavailableError

pytestmark = pytest.mark.integration

PATIENT = "P-10482"


@pytest.fixture
def memory(store):
    m = PatientMemory(PATIENT)
    m.set_fact(KIND_MEDICATION, "drug_a", {"reason": "adverse reaction"},
               status=STATUS_CONTRAINDICATED)
    m.set_fact(KIND_ALLERGY, "penicillin", {"reaction": "anaphylaxis"},
               status="documented")
    m.log_event(ClinicalEvent(EVENT_MEDICATION_ADMINISTERED, "Drug A administered",
                              "2026-01-02T08:00:00Z", KIND_MEDICATION, "drug_a", "ev-1"))
    m.log_event(ClinicalEvent(EVENT_ADVERSE_REACTION, "Adverse reaction to Drug A",
                              "2026-01-04T14:30:00Z", KIND_MEDICATION, "drug_a", "ev-2",
                              SEVERITY_CRITICAL))
    return m


# ---- the headline rule --------------------------------------------------

def test_unsourced_claim_is_rejected_however_plausible(memory):
    """The core guarantee. This claim is clinically reasonable and entirely
    unsourced, and that alone is disqualifying."""
    check = resolve_claim(memory, "Patient tolerates beta blockers well", None, None)
    assert check.supported is False
    assert check.rejection is RejectionReason.NO_CITATION
    assert "unsourced" in check.reason


@pytest.mark.parametrize("kind,name", [
    (KIND_MEDICATION, None), (None, "drug_a"), ("", ""), (KIND_MEDICATION, ""),
])
def test_partial_citations_are_still_unsourced(memory, kind, name):
    assert resolve_claim(memory, "some claim", kind, name).rejection \
        is RejectionReason.NO_CITATION


def test_claim_citing_a_record_that_does_not_exist_is_rejected(memory):
    check = resolve_claim(memory, "Patient is on Drug Z", KIND_MEDICATION, "drug_z")
    assert check.supported is False
    assert check.rejection is RejectionReason.NOT_IN_MEMORY


# ---- support paths ------------------------------------------------------

def test_claim_backed_by_a_current_fact_carries_status_and_body(memory):
    check = resolve_claim(memory, "Drug A is contraindicated",
                          KIND_MEDICATION, "drug_a")
    assert check.supported is True
    assert check.fact_status == STATUS_CONTRAINDICATED
    assert check.fact_body == {"reason": "adverse reaction"}
    assert check.has_current_fact is True


def test_supported_claim_cites_its_source_events_chronologically(memory):
    check = resolve_claim(memory, "Drug A caused a reaction", KIND_MEDICATION, "drug_a")
    assert [e.source_id for e in check.source_events] == ["ev-1", "ev-2"]
    assert check.source_events[1].severity == SEVERITY_CRITICAL
    assert check.source_events[1].event_type == EVENT_ADVERSE_REACTION


def test_history_only_claim_is_supported_without_a_current_fact(store):
    """Something that happened but has no standing WARM row is still evidence."""
    m = PatientMemory(PATIENT)
    m.log_event(ClinicalEvent(EVENT_MEDICATION_DISCONTINUED, "Drug Q stopped",
                              "2026-01-06T00:00:00Z", KIND_MEDICATION, "drug_q", "ev-9"))
    check = resolve_claim(m, "Drug Q was discontinued", KIND_MEDICATION, "drug_q")
    assert check.supported is True
    assert check.has_current_fact is False
    assert [e.source_id for e in check.source_events] == ["ev-9"]


def test_fact_without_events_is_supported_with_no_citations(memory):
    check = resolve_claim(memory, "Penicillin allergy documented",
                          KIND_ALLERGY, "penicillin")
    assert check.supported is True
    assert check.source_events == ()


# ---- structural matching, not substring ---------------------------------

def test_events_are_matched_structurally_not_by_substring(store):
    """A substring matcher would let one drug's history vouch for another whose
    name it contains. Structural matching on the stored pointer must not."""
    m = PatientMemory(PATIENT)
    m.log_event(ClinicalEvent(EVENT_ADVERSE_REACTION, "Reaction to Drug A Extended",
                              "2026-01-04T00:00:00Z", KIND_MEDICATION,
                              "drug_a_extended", "ev-x", SEVERITY_CRITICAL))

    borrowed = resolve_claim(m, "Drug A caused a reaction", KIND_MEDICATION, "drug_a")
    assert borrowed.supported is False, "one drug's event vouched for another"
    assert borrowed.rejection is RejectionReason.NOT_IN_MEMORY

    real = resolve_claim(m, "Drug A Extended caused a reaction",
                         KIND_MEDICATION, "drug_a_extended")
    assert real.supported is True


def test_kind_must_match_too(memory):
    """drug_a exists under medication; the same name under allergy does not."""
    check = resolve_claim(memory, "Allergy to drug A", KIND_ALLERGY, "drug_a")
    assert check.supported is False
    assert check.rejection is RejectionReason.NOT_IN_MEMORY


# ---- untrusted model output ---------------------------------------------

def test_unknown_kind_is_rejected(memory):
    check = resolve_claim(memory, "Patient horoscope favourable",
                          "astrology", "leo")
    assert check.rejection is RejectionReason.UNKNOWN_KIND


@pytest.mark.parametrize("name", ["drug; rm -rf /", 'drug"a', "drug|a", "drug`a`"])
def test_unsafe_identifiers_are_refused_not_merely_absent(memory, name):
    """Sibyl does not validate identifiers on read, so the resolver must --
    otherwise these report as 'not in memory' and the distinction is lost."""
    check = resolve_claim(memory, "claim", KIND_MEDICATION, name)
    assert check.rejection is RejectionReason.INVALID_IDENTIFIER


@pytest.mark.parametrize("text", ["", "   ", None, 123])
def test_malformed_claim_text_is_rejected(memory, text):
    check = resolve_claim(memory, text, KIND_MEDICATION, "drug_a")
    assert check.supported is False
    assert check.rejection is RejectionReason.MALFORMED


def test_non_string_citation_types_are_rejected(memory):
    assert resolve_claim(memory, "claim", 42, ["drug_a"]).rejection \
        is RejectionReason.MALFORMED


# ---- batch behaviour ----------------------------------------------------

def test_resolve_all_preserves_order_and_survives_garbage(memory):
    proposed = [
        {"text": "Drug A is contraindicated", "related_kind": KIND_MEDICATION,
         "related_name": "drug_a"},
        {"text": "Patient is fine"},
        "not even a dict",
        {"text": "Drug Z prescribed", "related_kind": KIND_MEDICATION,
         "related_name": "drug_z"},
    ]
    checks = resolve_all(memory, proposed)
    assert len(checks) == 4
    assert [c.supported for c in checks] == [True, False, False, False]
    assert checks[1].rejection is RejectionReason.NO_CITATION
    assert checks[2].rejection is RejectionReason.MALFORMED
    assert checks[3].rejection is RejectionReason.NOT_IN_MEMORY


def test_resolution_is_deterministic(memory):
    args = ("Drug A is contraindicated", KIND_MEDICATION, "drug_a")
    assert resolve_claim(memory, *args) == resolve_claim(memory, *args)


# ---- failure stays loud -------------------------------------------------

def test_resolver_cannot_support_a_claim_without_the_memory_layer(memory, store):
    """Delete Sibyl and nothing can be verified -- the claim above was
    supported a moment ago and now cannot even be attempted."""
    store.unlink()
    with pytest.raises(SibylUnavailableError):
        PatientMemory(PATIENT)
