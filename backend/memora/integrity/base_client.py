"""Base Sepolia contract interaction.

Deployed registry: see BASE_COMMITMENT_CONTRACT_ADDRESS. The contract stores a
digest, a timestamp and a committer address, and rejects re-committing a hash
that already exists -- so a recorded timestamp is always the FIRST time that
approved state existed.
"""

import logging
import time

from eth_account import Account
from web3 import Web3
from web3.exceptions import ContractLogicError

from memora.config import settings
from memora.integrity.errors import BaseUnavailableError, CommitmentExistsError

log = logging.getLogger("memora.integrity")

COMMITMENT_ABI = [
    {
        "inputs": [
            {"name": "commitmentHash", "type": "bytes32"},
            {"name": "label", "type": "string"},
        ],
        "name": "commit", "outputs": [],
        "stateMutability": "nonpayable", "type": "function",
    },
    {
        "inputs": [{"name": "commitmentHash", "type": "bytes32"}],
        "name": "verify",
        "outputs": [
            {"name": "exists", "type": "bool"},
            {"name": "timestamp", "type": "uint64"},
            {"name": "committer", "type": "address"},
        ],
        "stateMutability": "view", "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "committer", "type": "address"},
            {"indexed": True, "name": "commitmentHash", "type": "bytes32"},
            {"indexed": False, "name": "timestamp", "type": "uint64"},
            {"indexed": False, "name": "label", "type": "string"},
        ],
        "name": "StateCommitted", "type": "event",
    },
    {
        "inputs": [], "name": "totalCommitments",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view", "type": "function",
    },
]


def _normalise_key(key: str) -> str:
    key = key.strip()
    return key if key.startswith("0x") else "0x" + key


def get_web3() -> Web3:
    if not settings.base_rpc_url:
        raise BaseUnavailableError("BASE_RPC_URL is not set.")
    w3 = Web3(Web3.HTTPProvider(settings.base_rpc_url))
    if not w3.is_connected():
        raise BaseUnavailableError(f"Cannot reach Base RPC at {settings.base_rpc_url}")
    return w3


def get_contract(w3: Web3 | None = None):
    if not settings.base_commitment_contract_address:
        raise BaseUnavailableError("BASE_COMMITMENT_CONTRACT_ADDRESS is not set.")
    w3 = w3 or get_web3()
    return w3.eth.contract(
        address=Web3.to_checksum_address(settings.base_commitment_contract_address),
        abi=COMMITMENT_ABI,
    )


def _await_readable(contract, commitment_hash: bytes,
                    attempts: int = 12, delay: float = 1.0) -> bool:
    """Poll until a just-committed digest reads back.

    The public Base Sepolia RPC is load balanced, and eth_call immediately
    after wait_for_transaction_receipt can land on a node that has not applied
    the block yet -- it returns exists=False for a commitment that is genuinely
    onchain. Observed directly: the same query returned False and then True
    seconds later, with totalCommitments equally stale.

    This is eventual consistency across nodes, not an unconfirmed write: the
    receipt already reported status 1. Polling makes the returned tx_hash mean
    what a caller expects -- that the state is readable now.
    """
    for attempt in range(attempts):
        if contract.functions.verify(commitment_hash).call()[0]:
            return True
        if attempt < attempts - 1:
            time.sleep(delay)
    return False


def verify_hash(commitment_hash: bytes) -> dict:
    """Read-only check. Cheap, no key required, no gas."""
    contract = get_contract()
    exists, timestamp, committer = contract.functions.verify(commitment_hash).call()
    return {"exists": exists, "timestamp": int(timestamp), "committer": committer}


def commit_hash(commitment_hash: bytes, label: str) -> dict:
    """Anchor a digest onchain and wait for the receipt.

    Raises CommitmentExistsError if this exact state was already committed --
    that is the contract refusing to overwrite an earlier timestamp, not a
    failure to be retried.
    """
    if not settings.base_private_key:
        raise BaseUnavailableError("BASE_PRIVATE_KEY is not set.")

    w3 = get_web3()
    account = Account.from_key(_normalise_key(settings.base_private_key))
    contract = get_contract(w3)

    already = contract.functions.verify(commitment_hash).call()
    if already[0]:
        raise CommitmentExistsError(
            f"This approved state was already committed at unix {already[1]}."
        )

    fn = contract.functions.commit(commitment_hash, label)
    try:
        gas = int(fn.estimate_gas({"from": account.address}) * 1.2)
    except ContractLogicError as e:
        raise CommitmentExistsError(f"Contract rejected the commitment: {e}") from e

    tx = fn.build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": gas,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if receipt["status"] != 1:
        raise BaseUnavailableError(f"Commitment transaction reverted: {tx_hash.hex()}")

    tx_hex = tx_hash.hex()
    if not tx_hex.startswith("0x"):
        tx_hex = "0x" + tx_hex

    if not _await_readable(contract, commitment_hash):
        raise BaseUnavailableError(
            f"Commitment {tx_hex} was mined in block {receipt['blockNumber']} but is "
            "not readable from the RPC endpoint. Retry the read shortly."
        )

    log.info("committed %s in block %s", tx_hex, receipt["blockNumber"])
    return {
        "tx_hash": tx_hex,
        "block_number": receipt["blockNumber"],
        "gas_used": receipt["gasUsed"],
        "committer": account.address,
        "basescan_url": f"https://sepolia.basescan.org/tx/{tx_hex}",
    }
