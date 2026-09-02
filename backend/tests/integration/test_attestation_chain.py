"""EIP-712 attestation against the REAL deployed contract on Base Sepolia.

Tests marked `chain` send real transactions and cost testnet gas. There is no
local fork here: what needs proving is that the deployed contract enforces
replay protection, not that a simulation of it does.

Deselect with `-m "not chain"`.
"""

import time
import uuid

import pytest
from web3 import Web3

from memora.attestation.chain import (
    get_contract,
    get_web3,
    next_nonce,
    submit_attestation,
    verify_onchain,
)
from memora.attestation.domain import (
    DOMAIN_NAME,
    DOMAIN_VERSION,
    build_domain,
)
from memora.attestation.keys import synthetic_address
from memora.attestation.sign import sign_attestation
from memora.integrity.errors import CommitmentExistsError

pytestmark = pytest.mark.chain

CLINICIAN = "dr_maya"


def _unique_state() -> bytes:
    return Web3.keccak(text=f"memora-test-{uuid.uuid4()}")


def _sign_fresh(state_hash: bytes, nonce: int | None = None):
    signer = synthetic_address(CLINICIAN)
    return sign_attestation(
        clinician_id=CLINICIAN, state_hash=state_hash,
        evidence_root=Web3.keccak(text="evidence"),
        context_hash=Web3.keccak(text="icu_to_ward"),
        memory_version=7,
        nonce=next_nonce(signer) if nonce is None else nonce)


# ---- read-only ----------------------------------------------------------

def test_contract_is_deployed_on_base_sepolia():
    w3 = get_web3()
    assert w3.eth.chain_id == 84532
    assert len(w3.eth.get_code(get_contract(w3).address)) > 2


def test_domain_separator_matches_the_deployed_contract():
    """The highest-risk silent failure. If these diverge, every signature is
    valid off-chain and rejected on-chain, with no clear reason."""
    from eth_abi import encode
    from eth_utils import keccak

    onchain = get_contract().functions.domainSeparator().call()
    domain = build_domain()
    local = keccak(encode(
        ["bytes32", "bytes32", "bytes32", "uint256", "address"],
        [keccak(text="EIP712Domain(string name,string version,uint256 chainId,"
                     "address verifyingContract)"),
         keccak(text=DOMAIN_NAME), keccak(text=DOMAIN_VERSION),
         domain["chainId"],
         Web3.to_checksum_address(domain["verifyingContract"])]))
    assert onchain == local


def test_unattested_state_does_not_exist():
    assert verify_onchain(_unique_state())["exists"] is False


# ---- the real round trip ------------------------------------------------

def test_sign_submit_and_verify_a_real_attestation():
    state = _unique_state()
    signed = _sign_fresh(state)
    assert verify_onchain(state)["exists"] is False

    receipt = submit_attestation(signed)
    assert receipt["tx_hash"].startswith("0x")
    assert receipt["block_number"] > 0

    confirmed = verify_onchain(state)
    assert confirmed["exists"] is True
    assert confirmed["signer"] == signed.signer
    assert confirmed["memory_version"] == 7
    assert confirmed["timestamp"] > 0


def test_the_relayer_is_not_the_signer():
    """The server pays gas; a synthetic demo clinician key signs. Submitting
    proves nothing about who approved -- that separation is the point."""
    state = _unique_state()
    receipt = submit_attestation(_sign_fresh(state))
    signer = verify_onchain(state)["signer"]
    assert receipt["relayer"] != signer


def test_nonce_is_consumed_by_a_successful_attestation():
    signer = synthetic_address(CLINICIAN)
    before = next_nonce(signer)
    submit_attestation(_sign_fresh(_unique_state()))
    assert next_nonce(signer) == before + 1


# ---- REPLAY PROTECTION, proven against the deployed contract ------------

def test_the_same_state_cannot_be_attested_twice():
    state = _unique_state()
    submit_attestation(_sign_fresh(state))
    original = verify_onchain(state)["timestamp"]

    with pytest.raises(CommitmentExistsError):
        submit_attestation(_sign_fresh(state))

    assert verify_onchain(state)["timestamp"] == original, \
        "the first attestation time must survive"


def test_reusing_a_consumed_nonce_is_refused():
    """The actual replay proof: a different state, signed with a nonce that has
    already been used, must not be accepted."""
    signer = synthetic_address(CLINICIAN)
    stale_nonce = next_nonce(signer)
    submit_attestation(_sign_fresh(_unique_state()))   # consumes stale_nonce

    replayed = _sign_fresh(_unique_state(), nonce=stale_nonce)
    with pytest.raises(CommitmentExistsError):
        submit_attestation(replayed)


def test_an_expired_attestation_is_refused_by_the_contract():
    signer = synthetic_address(CLINICIAN)
    past = int(time.time()) - 7200
    expired = sign_attestation(
        clinician_id=CLINICIAN, state_hash=_unique_state(),
        evidence_root=Web3.keccak(text="e"), context_hash=Web3.keccak(text="c"),
        memory_version=1, nonce=next_nonce(signer),
        issued_at=past, ttl_seconds=60)
    with pytest.raises(CommitmentExistsError):
        submit_attestation(expired)
