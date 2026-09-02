"""Shared fixtures.

Every fixture here builds a REAL Sibyl store on disk. Nothing in this suite is
mocked, stubbed or faked: the repository layer is exercised against the actual
sibyl-memory-client, because the bug that motivated this rewrite (reading
.get("status") off an entity row instead of its body) passed a mocked test
while being broken in production.
"""

import pytest
from sibyl_memory_client import MemoryClient

from memora.config import settings


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A real, initialised, empty Sibyl store, wired into settings."""
    db_path = tmp_path / "memory.db"
    MemoryClient.local(str(db_path))  # creates the file + applies the schema
    monkeypatch.setattr(settings, "sibyl_db_path", db_path)
    return db_path


@pytest.fixture
def missing_store(tmp_path, monkeypatch):
    """settings points at a store that does not exist."""
    db_path = tmp_path / "gone" / "memory.db"
    monkeypatch.setattr(settings, "sibyl_db_path", db_path)
    return db_path
