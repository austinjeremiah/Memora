"""The hackathon's own pass/fail litmus test, automated.

    "delete the Sibyl Memory layer. Does the project still do what it claims?
     If yes, it is not load-bearing, and it is disqualified."

This is NOT a formality. sibyl-memory-client 0.7.0 silently recreates an empty
store when memory.db is missing -- MemoryClient.local() does not raise, it
returns a working client over an empty database. Without the preflight guard
MEMORA would answer with an empty result set instead of refusing, and would
fail this criterion while every other test stayed green.

If any test in this file fails, that is a failing build, not a flaky test.
"""

import pytest

from memora.ontology.kinds import KIND_MEDICATION, STATUS_ACTIVE
from memora.sibyl.client import PatientMemory
from memora.sibyl.errors import SibylPatientUnknownError, SibylUnavailableError

pytestmark = pytest.mark.compliance


def test_deleting_the_store_makes_memora_refuse_to_answer(store):
    """Write history, delete the memory layer, confirm MEMORA cannot answer."""
    m = PatientMemory("P-10482")
    m.set_fact(KIND_MEDICATION, "drug_a", {"note": "on admission"}, status=STATUS_ACTIVE)
    assert m.get_fact_body(KIND_MEDICATION, "drug_a") == {"note": "on admission"}

    # Delete the Sibyl Memory layer, exactly as a judge would.
    store.unlink()
    for sidecar in ("-wal", "-shm"):
        p = store.with_name(store.name + sidecar)
        if p.exists():
            p.unlink()

    with pytest.raises(SibylUnavailableError):
        PatientMemory("P-10482")

    # And it must not have quietly recreated the store on the way out.
    assert not store.exists(), "the store was recreated -- the guard ran too late"


def test_store_replaced_by_a_non_sibyl_file_is_refused(store):
    store.write_bytes(b"this is not a sqlite database, it is a decoy")
    with pytest.raises(SibylUnavailableError):
        PatientMemory("P-10482")


def test_empty_store_file_is_refused(store):
    store.write_bytes(b"")
    with pytest.raises(SibylUnavailableError):
        PatientMemory("P-10482")


def test_missing_store_is_refused_before_any_client_is_built(missing_store):
    with pytest.raises(SibylUnavailableError):
        PatientMemory("P-10482")
    assert not missing_store.exists()


def test_healthy_store_with_no_history_is_a_different_failure(store):
    """An empty-but-valid store is 'this patient is unknown', not 'memory is
    gone'. Conflating the two would let a genuinely deleted layer look like an
    ordinary empty patient."""
    with pytest.raises(SibylPatientUnknownError):
        PatientMemory("P-10482", require_data=True)

    # ...and the same store answers normally once history exists.
    PatientMemory("P-10482").set_fact(
        KIND_MEDICATION, "drug_a", {"n": 1}, status=STATUS_ACTIVE
    )
    m = PatientMemory("P-10482", require_data=True)
    assert m.get_fact_body(KIND_MEDICATION, "drug_a") == {"n": 1}
