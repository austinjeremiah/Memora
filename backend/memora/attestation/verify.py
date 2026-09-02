"""Recovering and checking an attestation's signer, off-chain.

Two separate questions, and conflating them would be the bug:

  1. Is the signature cryptographically valid for this exact typed data?
  2. Is the recovered address one MEMORA authorises to sign?

A perfectly valid signature from an unknown key answers yes to the first and no
to the second. Both must hold.
"""

import time
from dataclasses import dataclass

from eth_account import Account
from eth_account.messages import encode_typed_data

from memora.attestation.domain import ATTESTATION_TYPES, build_domain, build_message
from memora.attestation.keys import clinician_for_address, is_authorized


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    recovered_signer: str | None = None
    clinician_id: str | None = None
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.valid


def recover_signer(state_hash: bytes, evidence_root: bytes, context_hash: bytes,
                   memory_version: int, issued_at: int, expires_at: int,
                   nonce: int, signature: str,
                   verifying_contract: str | None = None) -> str:
    """The address that produced this signature over this exact typed data."""
    signable = encode_typed_data(
        build_domain(verifying_contract),
        ATTESTATION_TYPES,
        build_message(state_hash, evidence_root, context_hash,
                      memory_version, issued_at, expires_at, nonce),
    )
    return Account.recover_message(signable, signature=signature)


def verify_attestation(state_hash: bytes, evidence_root: bytes,
                       context_hash: bytes, memory_version: int,
                       issued_at: int, expires_at: int, nonce: int,
                       signature: str, expected_signer: str | None = None,
                       now: int | None = None,
                       verifying_contract: str | None = None) -> VerificationResult:
    """Full off-chain check: recovery, authorisation, expiry.

    The contract enforces expiry and nonce on-chain too. Checking here as well
    is not redundant -- it means a bad attestation is refused before a
    transaction is paid for, and the failure names the actual reason instead of
    surfacing as a revert string.
    """
    try:
        recovered = recover_signer(state_hash, evidence_root, context_hash,
                                   memory_version, issued_at, expires_at,
                                   nonce, signature, verifying_contract)
    except (ValueError, TypeError, Exception) as e:  # noqa: BLE001 - untrusted input
        # Signature bytes arrive from outside; eth-account raises a range of
        # types for malformed input and a failure to recover is a verification
        # result, not a crash.
        return VerificationResult(False, reason=f"Signature could not be recovered: {e}")

    if expected_signer and recovered.lower() != expected_signer.lower():
        return VerificationResult(False, recovered_signer=recovered,
                                  reason="Signature does not match the claimed signer.")

    if not is_authorized(recovered):
        return VerificationResult(False, recovered_signer=recovered,
                                  reason="Signer is not an authorised MEMORA persona.")

    now = int(now if now is not None else time.time())
    if now > expires_at:
        return VerificationResult(False, recovered_signer=recovered,
                                  clinician_id=clinician_for_address(recovered),
                                  reason="Attestation has expired.")

    return VerificationResult(True, recovered_signer=recovered,
                              clinician_id=clinician_for_address(recovered))
