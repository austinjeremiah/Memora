"""MEMORA's Sibyl failure modes.

Every one of these propagates. Nothing in the repository layer catches a Sibyl
failure and substitutes a default, a cache, or an empty result -- a silent
fallback is exactly the hidden path that would let MEMORA answer without a real
memory read, and that fails the hackathon's load-bearing gate.
"""


class SibylError(Exception):
    """Base for every MEMORA-level Sibyl failure."""


class SibylUnavailableError(SibylError):
    """The Sibyl memory layer is missing or unusable.

    Raised when memory.db does not exist, is empty, is not a SQLite file, or
    carries no Sibyl schema. This is the error the compliance deletion test
    asserts and the error /handoff turns into a 503.
    """


class SibylPatientUnknownError(SibylError):
    """The store is healthy but holds no data for this patient's tenant."""


class SibylQuotaExceededError(SibylError):
    """A write would cross the Sibyl free-tier cap (5,242,880 bytes)."""
