"""Signing, recovery and authorisation. Real keys, real crypto, no chain."""

import time

import pytest

from memora.attestation.keys import (
    authorized_signers,
    clinician_for_address,
    is_authorized,
    synthetic_address,
    synthetic_private_key,
)
from memora.attestation.sign import sign_attestation
from memora.attestation.verify import recover_signer, verify_attestation
from memora.integrity.commitment import compute_context_hash, compute_evidence_root

ADDR = "0x8B289101a7d6Bd7d066526B7b8D899Df582dd6b5"
STATE = b"\x11" * 32
EVIDENCE = b"\x22" * 32
CONTEXT = b"\x33" * 32


def _sign(clinician="dr_maya", **kw):
    return sign_attestation(clinician_id=clinician, state_hash=STATE,
                            evidence_root=EVIDENCE, context_hash=CONTEXT,
                            memory_version=kw.pop("memory_version", 7),
                            nonce=kw.pop("nonce", 0),
                            verifying_contract=ADDR, **kw)


# ---- synthetic demo keys ------------------------------------------------

def test_keys_are_deterministic_across_runs():
    """Otherwise every restart produces a new signer, and previously attested
    states appear to come from an unknown party."""
    assert synthetic_private_key("dr_maya") == synthetic_private_key("dr_maya")
    assert synthetic_address("dr_maya") == synthetic_address("dr_maya")


def test_each_persona_has_a_distinct_key():
    addresses = set(authorized_signers())
    assert len(addresses) == len(authorized_signers())
    assert synthetic_address("dr_maya") != synthetic_address("dr_arun")


def test_unknown_clinician_has_no_key():
    with pytest.raises(KeyError):
        synthetic_private_key("dr_who")


def test_only_known_personas_are_authorised():
    assert is_authorized(synthetic_address("dr_maya")) is True
    assert is_authorized("0x0000000000000000000000000000000000000001") is False
    assert clinician_for_address(synthetic_address("dr_arun")) == "dr_arun"


# ---- signing ------------------------------------------------------------

def test_signature_recovers_to_the_signing_persona():
    signed = _sign()
    recovered = recover_signer(STATE, EVIDENCE, CONTEXT, signed.memory_version,
                               signed.issued_at, signed.expires_at, signed.nonce,
                               signed.signature, verifying_contract=ADDR)
    assert recovered == signed.signer == synthetic_address("dr_maya")


def test_full_verification_passes_for_a_fresh_signature():
    signed = _sign()
    result = verify_attestation(STATE, EVIDENCE, CONTEXT, signed.memory_version,
                                signed.issued_at, signed.expires_at, signed.nonce,
                                signed.signature, expected_signer=signed.signer,
                                verifying_contract=ADDR)
    assert result.valid is True
    assert result.clinician_id == "dr_maya"


def test_expired_attestation_is_refused():
    signed = _sign()
    result = verify_attestation(STATE, EVIDENCE, CONTEXT, signed.memory_version,
                                signed.issued_at, signed.expires_at, signed.nonce,
                                signed.signature, now=signed.expires_at + 1,
                                verifying_contract=ADDR)
    assert result.valid is False
    assert "expired" in result.reason.lower()


def test_a_deadline_is_always_set():
    signed = _sign()
    assert signed.expires_at > signed.issued_at
    assert signed.expires_at - signed.issued_at <= 3600


@pytest.mark.parametrize("field,value", [
    ("memory_version", 999), ("nonce", 42),
])
def test_tampering_with_any_signed_field_breaks_recovery(field, value):
    signed = _sign()
    kwargs = {"memory_version": signed.memory_version, "issued_at": signed.issued_at,
              "expires_at": signed.expires_at, "nonce": signed.nonce}
    kwargs[field] = value
    recovered = recover_signer(STATE, EVIDENCE, CONTEXT, signature=signed.signature,
                               verifying_contract=ADDR, **kwargs)
    assert recovered != signed.signer


def test_tampering_with_the_state_hash_breaks_recovery():
    signed = _sign()
    recovered = recover_signer(b"\xff" * 32, EVIDENCE, CONTEXT,
                               signed.memory_version, signed.issued_at,
                               signed.expires_at, signed.nonce, signed.signature,
                               verifying_contract=ADDR)
    assert recovered != signed.signer


def test_a_valid_signature_from_an_unknown_key_is_still_refused():
    """Cryptographically valid and not authorised are different questions."""
    from eth_account import Account

    from memora.attestation.domain import ATTESTATION_TYPES, build_domain, build_message
    stranger = Account.create()
    message = build_message(STATE, EVIDENCE, CONTEXT, 7, int(time.time()),
                            int(time.time()) + 900, 0)
    sig = Account.sign_typed_data(stranger.key, build_domain(ADDR),
                                  ATTESTATION_TYPES, message).signature.hex()
    result = verify_attestation(STATE, EVIDENCE, CONTEXT, 7, message["issuedAt"],
                                message["expiresAt"], 0, "0x" + sig.removeprefix("0x"),
                                verifying_contract=ADDR)
    assert result.valid is False
    assert "not an authorised" in result.reason


def test_malformed_signature_is_a_result_not_a_crash():
    result = verify_attestation(STATE, EVIDENCE, CONTEXT, 7, 1, 2, 0, "0xdeadbeef",
                                verifying_contract=ADDR)
    assert result.valid is False


def test_different_contracts_produce_different_signatures():
    """The domain binds a signature to one deployment."""
    a = _sign()
    b = sign_attestation("dr_maya", STATE, EVIDENCE, CONTEXT, memory_version=7,
                         nonce=0, issued_at=a.issued_at,
                         verifying_contract="0xc54122E46DDbF4F88a8D23d32586DC1cB0d8888e")
    assert a.signature != b.signature


# ---- the two derived hashes ---------------------------------------------

def test_evidence_root_is_order_independent():
    """Two identical approvals must not attest to different roots."""
    assert compute_evidence_root(["e1", "e2", "e3"]) == \
           compute_evidence_root(["e3", "e1", "e2"])


def test_evidence_root_changes_with_the_evidence():
    assert compute_evidence_root(["e1"]) != compute_evidence_root(["e1", "e2"])


def test_context_hash_binds_situation_and_role():
    """A brief approved for ICU->ward must not read as approved for pre-op."""
    icu = compute_context_hash("icu_to_ward", "ward_physician")
    assert icu != compute_context_hash("pre_operative", "ward_physician")
    assert icu != compute_context_hash("icu_to_ward", "surgeon")
    assert icu == compute_context_hash("icu_to_ward", "ward_physician")
