"""EIP-712 domain and typed-data structure for a clinical attestation.

WHAT IS SIGNED, AND WHAT IS NOT. Every field is a hash, a counter or a
timestamp. No claim text, no clinical detail, no patient identifier reaches
this structure or the chain -- the same rule the original Commitment contract
already held to.

THE TYPEHASH IS FIXED THE MOMENT IT IS DEPLOYED. Field order and types here
must match Solidity's ATTESTATION_TYPEHASH string exactly; a mismatch produces
a digest that will never verify, and it fails silently rather than loudly.
Changing the struct after real attestations reference it invalidates every
prior one, so this is not a shape to iterate on casually.
"""

from memora.config import settings

DOMAIN_NAME = "MEMORA Clinical Integrity"
DOMAIN_VERSION = "1"

# Field ORDER here is load-bearing -- it must match the Solidity typehash
# string character for character. Asserted in tests/unit/test_attestation_domain.py.
ATTESTATION_TYPES = {
    "ClinicalAttestation": [
        {"name": "stateHash", "type": "bytes32"},
        {"name": "evidenceRoot", "type": "bytes32"},
        {"name": "contextHash", "type": "bytes32"},
        {"name": "memoryVersion", "type": "uint64"},
        {"name": "issuedAt", "type": "uint64"},
        {"name": "expiresAt", "type": "uint64"},
        {"name": "nonce", "type": "uint256"},
    ]
}

# The exact string Solidity keccak256()s to build ATTESTATION_TYPEHASH.
SOLIDITY_TYPE_STRING = (
    "ClinicalAttestation(bytes32 stateHash,bytes32 evidenceRoot,"
    "bytes32 contextHash,uint64 memoryVersion,uint64 issuedAt,"
    "uint64 expiresAt,uint256 nonce)"
)

# How long a signed attestation stays submittable. Short on purpose: the
# deadline is half of the replay protection (the nonce is the other half), and
# a long window is a long window in which a captured signature is still usable.
ATTESTATION_TTL_SECONDS = 900


def build_domain(verifying_contract: str | None = None) -> dict:
    """The EIP-712 domain separator inputs.

    chainId and verifyingContract are what bind a signature to THIS chain and
    THIS contract -- without them a signature captured here would be replayable
    against a different deployment.
    """
    contract = verifying_contract or settings.base_attestation_contract_address
    if not contract:
        raise ValueError(
            "No attestation contract address configured. Set "
            "BASE_ATTESTATION_CONTRACT_ADDRESS after deploying Attestation.sol."
        )
    return {
        "name": DOMAIN_NAME,
        "version": DOMAIN_VERSION,
        "chainId": settings.base_chain_id,
        "verifyingContract": contract,
    }


def build_message(state_hash: bytes, evidence_root: bytes, context_hash: bytes,
                  memory_version: int, issued_at: int, expires_at: int,
                  nonce: int) -> dict:
    """The message body, with key names exactly as the type declares them."""
    return {
        "stateHash": state_hash,
        "evidenceRoot": evidence_root,
        "contextHash": context_hash,
        "memoryVersion": int(memory_version),
        "issuedAt": int(issued_at),
        "expiresAt": int(expires_at),
        "nonce": int(nonce),
    }
