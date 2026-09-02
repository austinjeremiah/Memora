"""The authority check: may THIS clinician be shown THIS kind of record?

Deliberately small. Full RBAC is out of scope for the build; a demonstrable,
declared, deterministic permission boundary is in scope. The table is data, not
logic, so a judge can read the whole policy surface in one screen.
"""

from memora.context.situations import ClinicianRole
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_CARE_PHASE,
    KIND_DIAGNOSIS,
    KIND_LAB_TREND,
    KIND_MEDICATION,
    KIND_PROCEDURE,
)


class RolePermissions:
    __slots__ = ("can_approve_handoff", "can_view")

    def __init__(self, can_view: frozenset[str], can_approve_handoff: bool):
        self.can_view = can_view
        self.can_approve_handoff = can_approve_handoff


ROLE_PERMISSIONS: dict[ClinicianRole, RolePermissions] = {
    ClinicianRole.ICU_PHYSICIAN: RolePermissions(
        can_view=frozenset({KIND_MEDICATION, KIND_ALLERGY, KIND_DIAGNOSIS,
                            KIND_LAB_TREND, KIND_PROCEDURE, KIND_CARE_PHASE}),
        can_approve_handoff=True,
    ),
    ClinicianRole.WARD_PHYSICIAN: RolePermissions(
        # A ward physician receiving an ICU patient reads their labs -- that is
        # the entire point of medication reconciliation at a care transition.
        can_view=frozenset({KIND_MEDICATION, KIND_ALLERGY, KIND_DIAGNOSIS,
                            KIND_LAB_TREND, KIND_PROCEDURE, KIND_CARE_PHASE}),
        can_approve_handoff=True,
    ),
    # The surgeon is the narrow role: a pre-operative review needs allergies,
    # prior procedures and current medications. Diagnoses, lab trends and care
    # phase are outside that scope, and this is where the authority check is
    # demonstrated rather than on a ward physician reading a creatinine.
    ClinicianRole.SURGEON: RolePermissions(
        can_view=frozenset({KIND_ALLERGY, KIND_PROCEDURE, KIND_MEDICATION}),
        can_approve_handoff=False,
    ),
}


def has_authority(role: ClinicianRole, kind: str | None) -> bool:
    """Unknown roles and unknown kinds are denied, never defaulted to allowed.

    Failing closed matters here: a typo in a role name must not silently widen
    access, which is exactly what a .get(role, {}) default would do.
    """
    if kind is None:
        return False
    permissions = ROLE_PERMISSIONS.get(role)
    if permissions is None:
        return False
    return kind in permissions.can_view


def can_approve_handoff(role: ClinicianRole) -> bool:
    permissions = ROLE_PERMISSIONS.get(role)
    return permissions is not None and permissions.can_approve_handoff
