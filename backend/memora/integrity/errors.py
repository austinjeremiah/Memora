"""Integrity-layer failure modes."""


class IntegrityError(Exception):
    """Base for commitment failures."""


class BaseUnavailableError(IntegrityError):
    """Base RPC unreachable, or the integrity layer is not configured."""


class CommitmentExistsError(IntegrityError):
    """This exact approved state was already anchored onchain."""
