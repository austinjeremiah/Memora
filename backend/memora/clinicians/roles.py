"""Clinician personas for the demo.

Real authentication is explicitly out of scope for the build. What IS in scope
is that a request carries an identity whose role drives both retrieval and the
gate's authority check -- so the personas are a lookup table, and the role they
carry is load-bearing rather than cosmetic.

One persona per ClinicianRole, so every branch of the authority table is
reachable from the API without inventing a role at the call site.
"""

from dataclasses import dataclass

from memora.context.situations import ClinicianRole
from memora.gate.authority import can_approve_handoff


@dataclass(frozen=True)
class Clinician:
    id: str
    name: str
    role: ClinicianRole

    @property
    def can_approve_handoff(self) -> bool:
        return can_approve_handoff(self.role)


CLINICIANS: dict[str, Clinician] = {
    "dr_maya": Clinician("dr_maya", "Dr. Maya", ClinicianRole.ICU_PHYSICIAN),
    "dr_arun": Clinician("dr_arun", "Dr. Arun", ClinicianRole.WARD_PHYSICIAN),
    "dr_priya": Clinician("dr_priya", "Dr. Priya", ClinicianRole.SURGEON),
}


def get_clinician(clinician_id: str) -> Clinician | None:
    """Unknown ids return None rather than a default persona -- defaulting
    would silently grant whatever role the default happened to carry."""
    if not isinstance(clinician_id, str):
        return None
    return CLINICIANS.get(clinician_id)


def known_clinician_ids() -> tuple[str, ...]:
    return tuple(CLINICIANS)
