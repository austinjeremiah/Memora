"""Signing a clinical attestation with a synthetic demo clinician key.

The API shape here was verified by execution against the installed
eth-account 0.14.0, not taken from documentation:

    Account.sign_typed_data(key, domain, types, message) -> SignedMessage
    SignedMessage attributes: signature, message_hash, r, s, v   (snake_case)

`message_hash` is the EIP-712 digest, and it is exactly what Solidity's
_hashTypedDataV4 must reproduce for recovery to succeed. Confirmed identical to
keccak(b"\\x19\\x01" + header + body) from encode_typed_data.
"""

import time
from dataclasses import dataclass

from eth_account import Account

from memora.attestation.domain import (
    ATTESTATION_TTL_SECONDS,
    ATTESTATION_TYPES,
    build_domain,
    build_message,
)
from memora.attestation.keys import synthetic_address, synthetic_private_key


@dataclass(frozen=True)
class SignedAttestation:
    clinician_id: str
    signer: str                 # a SYNTHETIC DEMO address, never a real identity
    signature: str
    digest: str                 # the EIP-712 message hash
    state_hash: str
    evidence_root: str
    context_hash: str
    memory_version: int
    issued_at: int
    expires_at: int
    nonce: int

    def as_dict(self) -> dict:
        return {
            "clinician_id": self.clinician_id,
            "signer": self.signer,
            "signer_kind": "synthetic_demo_key",   # stated in the response too
            "signature": self.signature,
            "digest": self.digest,
            "state_hash": self.state_hash,
            "evidence_root": self.evidence_root,
            "context_hash": self.context_hash,
            "memory_version": self.memory_version,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "nonce": self.nonce,
        }

    def message_tuple(self) -> tuple:
        """Field order matching the Solidity struct exactly."""
        return (
            bytes.fromhex(self.state_hash[2:]),
            bytes.fromhex(self.evidence_root[2:]),
            bytes.fromhex(self.context_hash[2:]),
            self.memory_version,
            self.issued_at,
            self.expires_at,
            self.nonce,
        )


def sign_attestation(clinician_id: str, state_hash: bytes, evidence_root: bytes,
                     context_hash: bytes, memory_version: int, nonce: int,
                     issued_at: int | None = None,
                     ttl_seconds: int = ATTESTATION_TTL_SECONDS,
                     verifying_contract: str | None = None) -> SignedAttestation:
    """Sign one attestation. Returns everything needed to submit and verify it."""
    issued_at = int(issued_at if issued_at is not None else time.time())
    expires_at = issued_at + ttl_seconds

    domain = build_domain(verifying_contract)
    message = build_message(state_hash, evidence_root, context_hash,
                            memory_version, issued_at, expires_at, nonce)

    signed = Account.sign_typed_data(
        synthetic_private_key(clinician_id), domain, ATTESTATION_TYPES, message)

    return SignedAttestation(
        clinician_id=clinician_id,
        signer=synthetic_address(clinician_id),
        signature="0x" + signed.signature.hex().removeprefix("0x"),
        digest="0x" + signed.message_hash.hex().removeprefix("0x"),
        state_hash="0x" + state_hash.hex(),
        evidence_root="0x" + evidence_root.hex(),
        context_hash="0x" + context_hash.hex(),
        memory_version=memory_version,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
    )
