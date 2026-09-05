"""Wallet-mode attestation (Option B: config-registered addresses).

A clinician may sign from their own wallet only if that exact address is
mapped to them in config. Being merely authorised is not enough -- a wallet
registered to a different persona would produce a cryptographically valid
signature with the wrong attribution, which is the failure this guards.
"""


import pytest
from eth_account import Account
from fastapi.testclient import TestClient
from web3 import Web3

from memora.attestation.domain import ATTESTATION_TYPES, build_domain, build_message
from memora.attestation.keys import (
    authorized_signers,
    may_sign_as,
    registered_wallet,
    synthetic_address,
)
from memora.config import settings
from memora.main import app
from memora.ontology.kinds import KIND_MEDICATION, STATUS_ACTIVE
from memora.sibyl.client import PatientMemory

pytestmark = pytest.mark.integration

PATIENT = "P-WALLET"
WALLET = Account.from_key("0x" + "11" * 32)      # a stable test wallet


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def seeded(store):
    m = PatientMemory(PATIENT)
    m.set_fact(KIND_MEDICATION, "drug_b", {"label": "Drug B"}, status=STATUS_ACTIVE)
    return store


@pytest.fixture
def maya_wallet(monkeypatch):
    """dr_maya signs from a registered wallet; nobody else has one."""
    monkeypatch.setattr(settings, "clinician_wallets", {"dr_maya": WALLET.address})
    return WALLET


def _body(**kw):
    base = {"patient_id": PATIENT, "situation": "icu_to_ward",
            "clinician_id": "dr_maya",
            "claims": [{"text": "Drug B is active",
                        "related_kind": KIND_MEDICATION, "related_name": "drug_b"}]}
    base.update(kw)
    return base


# ---- authorisation model ------------------------------------------------

def test_registered_wallet_is_recognised(maya_wallet):
    assert registered_wallet("dr_maya") == WALLET.address
    assert registered_wallet("dr_arun") is None
    assert WALLET.address.lower() in {a.lower() for a in authorized_signers()}


def test_a_wallet_cannot_sign_as_a_different_clinician(maya_wallet):
    """The core of Option B. Valid signature, wrong attribution -- refused."""
    assert may_sign_as(WALLET.address, "dr_maya") is True
    assert may_sign_as(WALLET.address, "dr_arun") is False
    assert may_sign_as(WALLET.address, "dr_priya") is False


def test_synthetic_keys_still_work_when_no_wallet_is_registered():
    """The system must function with no wallet configured at all."""
    assert registered_wallet("dr_arun") is None
    assert may_sign_as(synthetic_address("dr_arun"), "dr_arun") is True


def test_an_unregistered_wallet_is_not_authorised(maya_wallet):
    stranger = Account.create()
    assert may_sign_as(stranger.address, "dr_maya") is False


# ---- step 1: the payload ------------------------------------------------

def test_payload_names_the_registered_wallet_as_expected_signer(client, seeded,
                                                                maya_wallet):
    r = client.post(f"/handoff/{PATIENT}/attestation-payload", json=_body())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["expected_signer"] == WALLET.address
    assert body["signer_mode"] == "wallet"


def test_payload_falls_back_to_the_synthetic_key_without_a_wallet(client, seeded):
    body = client.post(f"/handoff/{PATIENT}/attestation-payload",
                       json=_body()).json()
    assert body["signer_mode"] == "synthetic_demo_key"
    assert body["expected_signer"] == synthetic_address("dr_maya")


def test_payload_is_a_complete_eip712_structure(client, seeded, maya_wallet):
    body = client.post(f"/handoff/{PATIENT}/attestation-payload",
                       json=_body()).json()
    assert body["domain"]["chainId"] == 84532
    assert body["primary_type"] == "ClinicalAttestation"
    assert list(body["message"]) == [f["name"] for f in
                                     ATTESTATION_TYPES["ClinicalAttestation"]]
    assert body["message"]["stateHash"].startswith("0x")
    assert body["expires_at"] > body["issued_at"]
    assert body["memory_version"] >= 0


def test_payload_refuses_an_unverifiable_claim(client, seeded, maya_wallet):
    r = client.post(f"/handoff/{PATIENT}/attestation-payload", json=_body(
        claims=[{"text": "Drug Z is active", "related_kind": KIND_MEDICATION,
                 "related_name": "drug_z"}]))
    assert r.status_code == 409


def test_payload_requires_approval_authority(client, seeded, maya_wallet):
    r = client.post(f"/handoff/{PATIENT}/attestation-payload",
                    json=_body(clinician_id="dr_priya"))
    assert r.status_code == 403


def test_payload_is_503_without_the_memory_layer(client, seeded, maya_wallet):
    seeded.unlink()
    r = client.post(f"/handoff/{PATIENT}/attestation-payload", json=_body())
    assert r.status_code == 503


# ---- step 2: submitting a wallet signature ------------------------------

def _sign_payload(payload: dict, key) -> str:
    message = build_message(
        Web3.to_bytes(hexstr=payload["message"]["stateHash"]),
        Web3.to_bytes(hexstr=payload["message"]["evidenceRoot"]),
        Web3.to_bytes(hexstr=payload["message"]["contextHash"]),
        payload["message"]["memoryVersion"], payload["message"]["issuedAt"],
        payload["message"]["expiresAt"], payload["message"]["nonce"])
    signed = Account.sign_typed_data(key, build_domain(), ATTESTATION_TYPES, message)
    return "0x" + signed.signature.hex().removeprefix("0x")


def test_a_wallet_signing_as_another_clinician_is_refused(client, seeded,
                                                          maya_wallet):
    payload = client.post(f"/handoff/{PATIENT}/attestation-payload",
                          json=_body()).json()
    sig = _sign_payload(payload, WALLET.key)
    r = client.post(f"/handoff/{PATIENT}/attest", json=_body(
        clinician_id="dr_arun", signature=sig, signer=WALLET.address,
        issued_at=payload["issued_at"], expires_at=payload["expires_at"],
        nonce=payload["nonce"]))
    assert r.status_code == 403
    assert "not registered to sign as" in r.json()["detail"]


def test_wallet_mode_requires_the_signed_timestamps(client, seeded, maya_wallet):
    """The signature covers issued_at/expires_at/nonce -- omitting them would
    let the server verify against values the wallet never saw."""
    payload = client.post(f"/handoff/{PATIENT}/attestation-payload",
                          json=_body()).json()
    r = client.post(f"/handoff/{PATIENT}/attest", json=_body(
        signature=_sign_payload(payload, WALLET.key), signer=WALLET.address))
    assert r.status_code == 400
    assert "issued_at" in r.json()["detail"]


def test_a_tampered_signature_is_rejected(client, seeded, maya_wallet):
    payload = client.post(f"/handoff/{PATIENT}/attestation-payload",
                          json=_body()).json()
    stranger = Account.create()
    r = client.post(f"/handoff/{PATIENT}/attest", json=_body(
        signature=_sign_payload(payload, stranger.key), signer=WALLET.address,
        issued_at=payload["issued_at"], expires_at=payload["expires_at"],
        nonce=payload["nonce"]))
    assert r.status_code == 400
    assert "rejected" in r.json()["detail"].lower()


@pytest.mark.chain
def test_a_real_wallet_signature_is_recorded_onchain(client, seeded, maya_wallet):
    """The full wallet flow: server derives the state, wallet signs it, the
    contract verifies. Nothing is signed server-side."""
    import uuid
    marker = uuid.uuid4().hex[:8]
    PatientMemory(PATIENT).set_fact(KIND_MEDICATION, f"drug_{marker}",
                                    {"label": marker}, status=STATUS_ACTIVE)
    claims = [{"text": f"Marker {marker} is active",
               "related_kind": KIND_MEDICATION, "related_name": f"drug_{marker}"}]

    payload = client.post(f"/handoff/{PATIENT}/attestation-payload",
                          json=_body(claims=claims)).json()
    assert payload["expected_signer"] == WALLET.address

    r = client.post(f"/handoff/{PATIENT}/attest", json=_body(
        claims=claims, signature=_sign_payload(payload, WALLET.key),
        signer=WALLET.address, issued_at=payload["issued_at"],
        expires_at=payload["expires_at"], nonce=payload["nonce"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["signer"] == WALLET.address
    assert body["signer_kind"] == "registered_wallet"
    assert body["relayer"] != body["signer"], "the relayer must not be the signer"

    verified = client.get(f"/attestation/{body['state_hash']}/verify").json()
    assert verified["exists"] is True
    assert verified["signer"] == WALLET.address
