"""Patient scoping.

Verified against sibyl-memory-client 0.7.0 by execution, not by reading docs:

  * MemoryClient.local(path, tenant_id=...) accepts a tenant, and the tenant
    genuinely isolates rows -- a client on tenant B raises NotFoundError for an
    entity written by tenant A.
  * No per-call method accepts a tenant_id keyword; passing one raises
    TypeError. Scoping therefore happens once, at client construction.

So MEMORA uses one Sibyl tenant per patient. There is no name-prefixing
fallback and no search-prefix hack: isolation is a schema-level UNIQUE
constraint on (tenant_id, category, name), not a text convention.
"""

from dataclasses import dataclass

# sibyl-memory-client rejects these outright (verified: ';' is refused,
# '/' is accepted). Patient ids are synthetic and we control them, so we
# refuse anything questionable rather than let it reach the SDK.
_FORBIDDEN = set(';<>|"`\\') | {"\x00"}


def validate_patient_id(patient_id: str) -> str:
    if not isinstance(patient_id, str) or not patient_id.strip():
        raise ValueError("patient_id must be a non-empty string")
    bad = sorted(_FORBIDDEN & set(patient_id))
    if bad:
        raise ValueError(f"patient_id contains forbidden character(s): {' '.join(bad)}")
    if len(patient_id) > 512:
        raise ValueError(f"patient_id too long ({len(patient_id)} chars, max 512)")
    return patient_id


@dataclass(frozen=True)
class PatientScope:
    """The single place that decides how one patient's data is isolated."""

    patient_id: str

    def __post_init__(self) -> None:
        validate_patient_id(self.patient_id)

    @property
    def tenant_id(self) -> str:
        return f"patient-{self.patient_id}"
