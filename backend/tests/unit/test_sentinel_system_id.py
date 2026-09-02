"""Containment of Sentinel's reserved pseudo-tenant."""

import uuid

import pytest

from memora.sentinel.digest import SENTINEL_SYSTEM_ID
from memora.sibyl.keys import PatientScope, validate_patient_id


def test_reserved_system_id_cannot_collide_with_a_real_patient_id():
    """Synthea issues UUIDs. The reserved id must never parse as one, so an
    ingested patient can never shadow the system digest."""
    with pytest.raises(ValueError):
        uuid.UUID(SENTINEL_SYSTEM_ID)


def test_reserved_id_is_a_legal_sibyl_identifier():
    assert validate_patient_id(SENTINEL_SYSTEM_ID) == SENTINEL_SYSTEM_ID


def test_reserved_id_is_visibly_non_clinical():
    """A human reading a tenant list must not mistake it for a patient."""
    assert SENTINEL_SYSTEM_ID.startswith("__")
    assert SENTINEL_SYSTEM_ID.endswith("__")


def test_reserved_tenant_is_isolated_from_real_patients():
    system = PatientScope(SENTINEL_SYSTEM_ID).tenant_id
    real = PatientScope("c1735287-5150-97de-7eb5-4c1c22c2307e").tenant_id
    assert system != real
    assert system == "patient-__sentinel_system__"
