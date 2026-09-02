"""Submitting and reading attestations on Base Sepolia.

Mirrors the existing Commitment client's shape deliberately, including the
read-after-write poll: Base's public RPC is load balanced and an eth_call
immediately after a confirmed receipt can hit a node that has not applied the
block yet, returning exists=False for something genuinely onchain.
"""

import logging
import time

from eth_account import Account
from web3 import Web3
from web3.exceptions import ContractLogicError

from memora.attestation.sign import SignedAttestation
from memora.config import settings
from memora.integrity.errors import BaseUnavailableError, CommitmentExistsError

log = logging.getLogger("memora.attestation")

ATTESTATION_ABI = [
    {
        "inputs": [
            {"components": [
                {"name": "stateHash", "type": "bytes32"},
                {"name": "evidenceRoot", "type": "bytes32"},
                {"name": "contextHash", "type": "bytes32"},
                {"name": "memoryVersion", "type": "uint64"},
                {"name": "issuedAt", "type": "uint64"},
                {"name": "expiresAt", "type": "uint64"},
                {"name": "nonce", "type": "uint256"},
            ], "name": "a", "type": "tuple"},
            {"name": "signer", "type": "address"},
            {"name": "signature", "type": "bytes"},
        ],
        "name": "attest", "outputs": [],
        "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "stateHash", "type": "bytes32"}],
        "name": "verify",
        "outputs": [
            {"name": "exists", "type": "bool"},
            {"name": "signer", "type": "address"},
            {"name": "timestamp", "type": "uint64"},
            {"name": "memoryVersion", "type": "uint64"},
        ],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "nonces", "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [], "name": "totalAttestations",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [], "name": "domainSeparator",
        "outputs": [{"name": "", "type": "bytes32"}],
        "stateMutability": "view", "type": "function",
    },
]


def get_web3() -> Web3:
    w3 = Web3(Web3.HTTPProvider(settings.base_rpc_url))
    if not w3.is_connected():
        raise BaseUnavailableError(f"Cannot reach Base RPC at {settings.base_rpc_url}")
    return w3


def get_contract(w3: Web3 | None = None):
    if not settings.base_attestation_contract_address:
        raise BaseUnavailableError(
            "BASE_ATTESTATION_CONTRACT_ADDRESS is not set. Deploy Attestation.sol first.")
    w3 = w3 or get_web3()
    return w3.eth.contract(
        address=Web3.to_checksum_address(settings.base_attestation_contract_address),
        abi=ATTESTATION_ABI)


def next_nonce(signer: str) -> int:
    """The nonce this signer must use. Read from the contract, never guessed --
    a stale local counter would produce signatures that revert."""
    return int(get_contract().functions.nonces(
        Web3.to_checksum_address(signer)).call())


def verify_onchain(state_hash: bytes) -> dict:
    """Read-only. No key, no gas."""
    exists, signer, timestamp, memory_version = get_contract().functions.verify(
        state_hash).call()
    return {"exists": exists, "signer": signer, "timestamp": int(timestamp),
            "memory_version": int(memory_version)}


def _await_readable(contract, state_hash: bytes, attempts: int = 12,
                    delay: float = 1.0) -> bool:
    for attempt in range(attempts):
        if contract.functions.verify(state_hash).call()[0]:
            return True
        if attempt < attempts - 1:
            time.sleep(delay)
    return False


def submit_attestation(attestation: SignedAttestation) -> dict:
    """Submit a signed attestation. The CONTRACT verifies the signature.

    The relayer paying gas is not the signer, and cannot be: the signature is
    over typed data bound to this chain and contract, so submitting it proves
    nothing about who submitted it. That separation is the point -- a synthetic
    demo clinician signs, the server relays.
    """
    if not settings.base_private_key:
        raise BaseUnavailableError("BASE_PRIVATE_KEY is not set.")

    w3 = get_web3()
    contract = get_contract(w3)
    relayer = Account.from_key(
        settings.base_private_key if settings.base_private_key.startswith("0x")
        else "0x" + settings.base_private_key)

    state_hash = bytes.fromhex(attestation.state_hash[2:])
    if contract.functions.verify(state_hash).call()[0]:
        raise CommitmentExistsError(
            "This approved state has already been attested onchain.")

    fn = contract.functions.attest(
        attestation.message_tuple(),
        Web3.to_checksum_address(attestation.signer),
        bytes.fromhex(attestation.signature[2:]),
    )
    try:
        gas = int(fn.estimate_gas({"from": relayer.address}) * 1.2)
    except ContractLogicError as e:
        raise CommitmentExistsError(f"Contract rejected the attestation: {e}") from e

    tx = fn.build_transaction({
        "from": relayer.address,
        "nonce": w3.eth.get_transaction_count(relayer.address),
        "gas": gas,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id,
    })
    signed_tx = relayer.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if receipt["status"] != 1:
        raise BaseUnavailableError(f"Attestation transaction reverted: {tx_hash.hex()}")

    tx_hex = tx_hash.hex()
    if not tx_hex.startswith("0x"):
        tx_hex = "0x" + tx_hex

    if not _await_readable(contract, state_hash):
        raise BaseUnavailableError(
            f"Attestation {tx_hex} was mined in block {receipt['blockNumber']} but is "
            "not readable from the RPC endpoint. Retry the read shortly.")

    log.info("attested %s in block %s", tx_hex, receipt["blockNumber"])
    return {
        "tx_hash": tx_hex,
        "block_number": receipt["blockNumber"],
        "gas_used": receipt["gasUsed"],
        "relayer": relayer.address,
        "basescan_url": f"https://sepolia.basescan.org/tx/{tx_hex}",
    }
