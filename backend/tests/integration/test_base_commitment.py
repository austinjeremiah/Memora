"""Base Sepolia integrity commitment, against the real deployed contract.

Tests marked `chain` send REAL transactions to Base Sepolia and cost testnet
gas. Read-only verification needs no key and no gas. Nothing is simulated --
there is no local anvil fork here, because what needs proving is that the
deployed contract behaves, not that a simulation of it does.

Deselect with `-m "not chain"`.
"""

import uuid

import pytest

from memora.integrity.base_client import (
    commit_hash,
    get_contract,
    get_web3,
    verify_hash,
)
from memora.integrity.commitment import (
    canonical_commitment_payload,
    commitment_label,
    compute_commitment_hash,
)
from memora.integrity.errors import CommitmentExistsError


def _unique_digest() -> bytes:
    """A digest no previous run can have committed."""
    return compute_commitment_hash(canonical_commitment_payload(
        f"P-TEST-{uuid.uuid4()}", "icu_to_ward",
        [{"text": "test claim", "gate_result": "ALLOW"}]))


# ---- read-only: no key, no gas ------------------------------------------

@pytest.mark.chain
def test_connected_to_base_sepolia():
    w3 = get_web3()
    assert w3.is_connected()
    assert w3.eth.chain_id == 84532


@pytest.mark.chain
def test_contract_is_actually_deployed():
    w3 = get_web3()
    contract = get_contract(w3)
    assert len(w3.eth.get_code(contract.address)) > 2, "no bytecode at the address"


@pytest.mark.chain
def test_uncommitted_digest_does_not_exist():
    result = verify_hash(_unique_digest())
    assert result["exists"] is False
    assert result["timestamp"] == 0


# ---- state-changing: real testnet transaction ---------------------------

@pytest.mark.chain
def test_commit_then_verify_round_trips_onchain():
    digest = _unique_digest()
    assert verify_hash(digest)["exists"] is False

    receipt = commit_hash(digest, commitment_label("P-TEST", "icu_to_ward"))
    assert receipt["tx_hash"].startswith("0x")
    assert receipt["block_number"] > 0
    assert receipt["basescan_url"].endswith(receipt["tx_hash"])

    confirmed = verify_hash(digest)
    assert confirmed["exists"] is True
    assert confirmed["timestamp"] > 0
    assert confirmed["committer"] == receipt["committer"]


@pytest.mark.chain
def test_recommitting_the_same_state_is_refused():
    """The registry's whole value is that a timestamp is the FIRST time a state
    existed, so an overwrite must be impossible."""
    digest = _unique_digest()
    first = commit_hash(digest, "P-TEST:icu_to_ward")
    original = verify_hash(digest)["timestamp"]

    with pytest.raises(CommitmentExistsError):
        commit_hash(digest, "P-TEST:icu_to_ward")

    assert verify_hash(digest)["timestamp"] == original
    assert first["tx_hash"]
