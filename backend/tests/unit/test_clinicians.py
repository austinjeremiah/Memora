"""Clinician personas. Pure lookup -- no store needed."""

import pytest

from memora.clinicians.roles import CLINICIANS, get_clinician, known_clinician_ids
from memora.context.situations import ClinicianRole
from memora.gate.authority import ROLE_PERMISSIONS


def test_every_role_has_a_persona():
    """Otherwise a branch of the authority table is unreachable from the API."""
    covered = {c.role for c in CLINICIANS.values()}
    assert covered == set(ClinicianRole)


def test_persona_ids_match_their_keys():
    for key, clinician in CLINICIANS.items():
        assert clinician.id == key


def test_every_persona_role_is_in_the_authority_table():
    for clinician in CLINICIANS.values():
        assert clinician.role in ROLE_PERMISSIONS


def test_lookup_returns_the_persona():
    maya = get_clinician("dr_maya")
    assert maya.name == "Dr. Maya"
    assert maya.role is ClinicianRole.ICU_PHYSICIAN


@pytest.mark.parametrize("bad", ["nobody", "", None, 42, "DR_MAYA"])
def test_unknown_id_returns_none_never_a_default_persona(bad):
    assert get_clinician(bad) is None


def test_approval_rights_come_from_the_authority_table():
    assert get_clinician("dr_maya").can_approve_handoff is True
    assert get_clinician("dr_arun").can_approve_handoff is True
    assert get_clinician("dr_priya").can_approve_handoff is False


def test_known_ids_listed():
    assert set(known_clinician_ids()) == {"dr_maya", "dr_arun", "dr_priya"}
