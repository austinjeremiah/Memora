"""Fail-closed availability checks for the Sibyl memory layer.

WHY THIS MODULE EXISTS
----------------------
MemoryClient.local(path) does NOT raise when the store is missing. Verified by
execution against sibyl-memory-client 0.7.0:

    deleted memory.db.  exists: False
    REOPEN: NO RAISE - client constructed fine
            db recreated: True
            list_entities: []   read_events: []

It silently creates a fresh, empty database and carries on. Left unguarded that
turns the hackathon's own pass/fail litmus test -- "delete the Sibyl Memory
layer; does the project still do what it claims?" -- into a quiet success: the
API would answer 200 with an empty claim list instead of refusing.

So availability is asserted HERE, before the client is ever constructed, and
the failure is loud.
"""

from pathlib import Path

from memora.sibyl.errors import SibylPatientUnknownError, SibylUnavailableError

_SQLITE_MAGIC = b"SQLite format 3\x00"


def assert_store_available(db_path: Path) -> None:
    """Raise SibylUnavailableError unless db_path is a real, non-empty SQLite file.

    MUST be called before MemoryClient.local(), which would otherwise recreate
    the file and mask its absence.
    """
    if not db_path.exists():
        raise SibylUnavailableError(
            f"Sibyl memory store not found at {db_path}. MEMORA cannot reconstruct "
            "patient context without it and will not answer from anything else."
        )
    if not db_path.is_file():
        raise SibylUnavailableError(f"Sibyl memory path {db_path} is not a file.")

    size = db_path.stat().st_size
    if size == 0:
        raise SibylUnavailableError(f"Sibyl memory store at {db_path} is empty (0 bytes).")

    try:
        with db_path.open("rb") as fh:
            header = fh.read(16)
    except OSError as e:
        raise SibylUnavailableError(f"Sibyl memory store at {db_path} is unreadable: {e}") from e

    if header != _SQLITE_MAGIC:
        raise SibylUnavailableError(
            f"File at {db_path} is not a SQLite database (bad header). "
            "Refusing to treat it as a Sibyl memory store."
        )


def assert_schema_ready(client, db_path: Path) -> None:
    """Raise SibylUnavailableError unless the open store carries a Sibyl schema.

    Catches the case where the file is a valid SQLite database but not a Sibyl
    store (or a store whose schema failed to apply).
    """
    try:
        version = client.schema_version()
    except Exception as e:
        raise SibylUnavailableError(
            f"Could not read the Sibyl schema version at {db_path}: {e}"
        ) from e
    if version is None:
        raise SibylUnavailableError(
            f"No Sibyl schema present in {db_path} -- this is not an initialised memory store."
        )


def assert_patient_known(client, patient_id: str) -> None:
    """Raise SibylPatientUnknownError when the store holds nothing for this tenant.

    The store being healthy is a different condition from this patient having
    history. Retrieval paths require the latter; ingestion legitimately starts
    from nothing and must not call this.
    """
    if client.list_entities(limit=1):
        return
    if client.read_events(limit=1):
        return
    raise SibylPatientUnknownError(
        f"No memory found for patient {patient_id}. Nothing has been written to "
        f"tenant '{client.get_tenant()}'."
    )
