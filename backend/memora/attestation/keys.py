"""SYNTHETIC DEMO CLINICIAN KEYS.

Read this before using anything in this module.

These are NOT real clinician identities, NOT an authentication mechanism, and
NOT a claim that a named human signed anything. They are deterministic keypairs
derived from a configured seed, held server-side, so a hackathon demo can show
a cryptographically attributed signature end to end. A production system would
have the clinician hold their own key and sign in their own client; MEMORA does
not, and says so everywhere this appears -- in code, in the API response, and
in the README.

Derivation is deterministic (seed + clinician_id) so a persona's address is
stable across runs and restarts. Without that, every restart would produce a
new signer and previously attested states would appear to come from an unknown
party.
"""

import hashlib

from eth_account import Account

from memora.clinicians.roles import CLINICIANS
from memora.config import settings

# Used only when no seed is configured, so tests and local runs work without
# setup. It is checked in deliberately: these keys secure nothing, hold nothing,
# and exist on a testnet. A real secret would never be committed.
_DEFAULT_DEMO_SEED = "memora-synthetic-demo-clinicians-not-real-identities"


def _seed() -> str:
    return settings.attestation_seed or _DEFAULT_DEMO_SEED


def synthetic_private_key(clinician_id: str) -> str:
    """Deterministic demo key for a persona. Never a real clinician's key."""
    if clinician_id not in CLINICIANS:
        raise KeyError(f"Unknown clinician_id: {clinician_id}")
    digest = hashlib.sha256(f"{_seed()}:{clinician_id}".encode()).hexdigest()
    return "0x" + digest


def synthetic_address(clinician_id: str) -> str:
    return Account.from_key(synthetic_private_key(clinician_id)).address


def authorized_signers() -> dict[str, str]:
    """address -> clinician_id, for every persona that may sign.

    An address outside this map is not an authorised signer, however valid its
    signature is cryptographically -- a correct signature from an unknown party
    is exactly what this check exists to reject.
    """
    return {synthetic_address(cid): cid for cid in CLINICIANS}


def is_authorized(address: str) -> bool:
    return address in authorized_signers()


def clinician_for_address(address: str) -> str | None:
    return authorized_signers().get(address)
