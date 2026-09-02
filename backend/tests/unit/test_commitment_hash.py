"""Canonical serialisation and hashing. Pure -- no chain, no store."""

import pytest

from memora.integrity.commitment import (
    canonical_commitment_payload,
    canonical_json,
    commitment_label,
    compute_commitment_hash,
)

CLAIMS = [
    {"text": "Drug A is contraindicated", "gate_result": "NEEDS_REVIEW"},
    {"text": "Drug B is active", "gate_result": "ALLOW"},
]


def test_hash_is_stable_across_runs():
    a = compute_commitment_hash(canonical_commitment_payload("P-1", "icu_to_ward", CLAIMS))
    b = compute_commitment_hash(canonical_commitment_payload("P-1", "icu_to_ward", CLAIMS))
    assert a == b
    assert len(a) == 32


def test_claim_order_does_not_change_the_hash():
    """The same approved brief must hash identically however it was ordered."""
    forward = compute_commitment_hash(
        canonical_commitment_payload("P-1", "icu_to_ward", CLAIMS))
    reverse = compute_commitment_hash(
        canonical_commitment_payload("P-1", "icu_to_ward", list(reversed(CLAIMS))))
    assert forward == reverse


def test_changing_a_verdict_changes_the_hash():
    flipped = [{"text": CLAIMS[0]["text"], "gate_result": "ALLOW"}, CLAIMS[1]]
    assert compute_commitment_hash(
        canonical_commitment_payload("P-1", "icu_to_ward", CLAIMS)
    ) != compute_commitment_hash(
        canonical_commitment_payload("P-1", "icu_to_ward", flipped))


@pytest.mark.parametrize("patient,situation", [
    ("P-2", "icu_to_ward"), ("P-1", "discharge"),
])
def test_patient_and_situation_are_bound_into_the_hash(patient, situation):
    base = compute_commitment_hash(
        canonical_commitment_payload("P-1", "icu_to_ward", CLAIMS))
    other = compute_commitment_hash(
        canonical_commitment_payload(patient, situation, CLAIMS))
    assert base != other


def test_no_clinical_detail_reaches_the_payload():
    """Only claim text and verdict are hashed -- never record bodies."""
    payload = canonical_commitment_payload("P-1", "icu_to_ward", [
        {"text": "Drug A contraindicated", "gate_result": "NEEDS_REVIEW",
         "fact_body": {"secret": "should not be hashed"},
         "source_events": ["ev-1"]},
    ])
    blob = canonical_json(payload).decode()
    assert "secret" not in blob
    assert "ev-1" not in blob
    assert set(payload["claims"][0]) == {"text", "gate_result"}


def test_canonical_json_is_byte_stable_and_compact():
    blob = canonical_json(canonical_commitment_payload("P-1", "icu_to_ward", CLAIMS))
    assert b", " not in blob      # pinned separators, not default spacing
    assert blob == canonical_json(
        canonical_commitment_payload("P-1", "icu_to_ward", CLAIMS))


def test_label_carries_only_synthetic_identifiers():
    assert commitment_label("P-10482", "icu_to_ward") == "P-10482:icu_to_ward"
