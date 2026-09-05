"""The one place every Sibyl call in MEMORA happens.

Nothing outside this module imports sibyl_memory_client. One audited chokepoint,
not scattered raw calls.

Contracts below were confirmed by executing sibyl-memory-client 0.7.0, not by
reading its docs. The ones that differ from the published examples:

  * get_entity RAISES NotFoundError for a missing row; it never returns None.
  * Entity getters return the ROW -- {id, tenant_id, category, name, status,
    body, created_at, updated_at} -- so the clinical payload is row["body"] and
    the lifecycle marker is row["status"] (a real column, set via the status=
    keyword). Reading .get("status") off the row instead of the body is the
    subtle bug that silently disabled the policy rule in the original plan.
  * write_event is keyword-only (evaluated/acted/forward/extra/ts). Arbitrary
    keywords raise TypeError. Structured metadata goes in extra=, the real
    clinical time goes in ts=.
  * read_events defaults to limit=50, newest first -- it truncates history
    silently, so every read here passes an explicit limit.
  * get_state returns {"body": ..., "updated_at": ...}, so the payload is
    nested one level down.
  * The free-tier cap is 5,242,880 bytes, account-level and WAL-inclusive.
    free_tier_status() is authoritative; os.stat on memory.db is not.
"""

import logging

from sibyl_memory_client import MemoryClient
from sibyl_memory_client.exceptions import CapExceededError, NotFoundError

from memora.config import settings
from memora.ontology.events import ClinicalEvent
from memora.sibyl.errors import SibylQuotaExceededError, SibylUnavailableError
from memora.sibyl.keys import PatientScope
from memora.sibyl.preflight import (
    assert_patient_known,
    assert_schema_ready,
    assert_store_available,
)

log = logging.getLogger("memora.sibyl")

# HOT-state key holding the per-patient monotonic event counter.
MEMORY_VERSION_KEY = "memory_version"

# Read every tier well past any realistic per-patient volume. The SDK's own
# default of 50 would silently hide older history from the Evidence Resolver,
# which would then reject a true claim for lack of a source event.
FULL_READ_LIMIT = 1000


class PatientMemory:
    """Patient-scoped facade over Sibyl's five tiers.

    Isolation is a real Sibyl tenant (one per patient), not a naming convention.

    There is deliberately no try/except here that swallows a Sibyl error and
    returns a default. Every failure propagates so the caller has to handle it
    visibly. A repository that quietly degrades to "no data" is indistinguishable
    from one whose memory layer has been deleted.
    """

    def __init__(self, patient_id: str, *, require_data: bool = False):
        self.scope = PatientScope(patient_id=patient_id)
        self._quota_warned = False
        db_path = settings.sibyl_db_path

        # Order matters: the store must be proven to exist BEFORE the client is
        # constructed, because constructing it would create an empty one.
        assert_store_available(db_path)
        try:
            self._memory = MemoryClient.local(str(db_path), tenant_id=self.scope.tenant_id)
        except Exception as e:
            raise SibylUnavailableError(f"Could not open Sibyl memory store at {db_path}: {e}") from e
        assert_schema_ready(self._memory, db_path)

        if require_data:
            assert_patient_known(self._memory, patient_id)

    # ---- HOT: current situational context -------------------------------
    def set_context(self, key: str, body: dict) -> None:
        with self._quota_guard():
            self._memory.set_state(key, body)

    def get_context(self, key: str) -> dict | None:
        state = self._memory.get_state(key)
        return state["body"] if state else None

    # ---- WARM: current clinical facts -----------------------------------
    def set_fact(self, kind: str, name: str, body: dict, *, status: str | None = None) -> dict:
        """Write a current fact. `status` is a real indexed column, so lifecycle
        state belongs there rather than buried in the body -- it makes
        list_facts(status=...) a genuine query."""
        with self._quota_guard():
            return self._memory.set_entity(kind, name, body, status=status)

    def get_fact(self, kind: str, name: str) -> dict | None:
        """Return the full entity row, or None when absent.

        Translating NotFoundError into None here is the one place MEMORA is
        allowed to do so: absence is a legitimate answer that callers branch on,
        and it is not the same thing as the memory layer being unavailable --
        which still raises, loudly, from preflight.
        """
        try:
            return self._memory.get_entity(kind, name)
        except NotFoundError:
            return None

    def get_fact_body(self, kind: str, name: str) -> dict | None:
        row = self.get_fact(kind, name)
        return row["body"] if row else None

    def list_facts(self, kind: str | None = None, *, status: str | None = None,
                   limit: int = FULL_READ_LIMIT) -> list[dict]:
        """Complete enumeration of a kind. The SDK provides this directly; the
        original plan's FTS-search workaround (and its fallback index-entity
        design) were unnecessary and would have under-returned on rank."""
        return self._memory.list_entities(kind, status=status, limit=limit)

    # ---- COLD: append-only history --------------------------------------
    def log_event(self, event: ClinicalEvent) -> str:
        with self._quota_guard():
            event_id = self._memory.write_event(
                acted=[event.summary],
                extra=event.to_extra(),
                ts=event.timestamp or None,
            )
        self._bump_memory_version()
        return event_id

    # ---- Memory version -------------------------------------------------
    #
    # A monotonic per-patient counter of how many things have been recorded.
    # An attestation cites it so a signature is bound to a specific point in
    # this patient's history: the same approved brief signed before and after
    # new events are recorded produces different attestations, which is what
    # makes "this was true as of this state" a checkable claim.
    #
    # It is deliberately NOT derived from len(read_history()) -- that depends
    # on the query's limit and is not a stable count. It is incremented in the
    # same write path that appends to the journal, and stored as HOT state,
    # which is an upsert on (tenant, key): one row per patient no matter how
    # many times it is bumped, so the row-count discipline is preserved.

    def _bump_memory_version(self) -> int:
        current = self.memory_version()
        self._memory.set_state(MEMORY_VERSION_KEY, {"n": current + 1})
        return current + 1

    def memory_version(self) -> int:
        state = self._memory.get_state(MEMORY_VERSION_KEY)
        if not state:
            return 0
        try:
            return int(state["body"]["n"])
        except (KeyError, TypeError, ValueError):
            return 0

    def read_history(self, *, limit: int = FULL_READ_LIMIT,
                     since: str | None = None, until: str | None = None) -> list[dict]:
        return self._memory.read_events(limit=limit, since=since, until=until)

    # ---- REFERENCE: static lookup documents -----------------------------
    def set_reference(self, key: str, body: dict) -> None:
        with self._quota_guard():
            self._memory.set_reference(key, body)

    def get_reference(self, key: str) -> dict | None:
        """The SDK stores a dict body as a JSON string and hands it back as a
        string, so it is decoded here rather than at every call site."""
        import json

        ref = self._memory.get_reference(key)
        if ref is None:
            return None
        body = ref["body"]
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                pass
        return {"body": body, "metadata": ref["metadata"], "updated_at": ref["updated_at"]}

    # ---- ARCHIVE: retire, never delete ----------------------------------
    def archive_fact(self, kind: str, name: str, reason: str | None = None) -> dict:
        """Retire a fact, recoverably.

        delete_entity is never called on clinical data anywhere in MEMORA.
        Note archive is itself cap-gated by the SDK (it copies the body before
        removing the row), so it can fail near the quota -- hence the guard.
        """
        with self._quota_guard():
            return self._memory.archive_entity(kind, name, reason=reason)

    # ---- Search ---------------------------------------------------------
    def search(self, query: str, *, kind: str | None = None, limit: int = 20) -> list[dict]:
        """FTS5 keyword search, already tenant-scoped by the client."""
        return self._memory.search_entities(query, limit=limit, category=kind)

    # ---- Quota ----------------------------------------------------------
    def quota(self) -> dict:
        return self._memory.free_tier_status()

    class _QuotaGuard:
        def __init__(self, outer: "PatientMemory"):
            self._outer = outer

        def __enter__(self):
            status = self._outer._memory.free_tier_status()
            if status.get("at_or_above_cap"):
                raise SibylQuotaExceededError(
                    f"Sibyl free-tier cap reached ({status['db_size_bytes']:,} of "
                    f"{status['soft_cap_bytes']:,} bytes). Trim the dataset or upgrade."
                )
            if status.get("at_or_above_warning") and not self._outer._quota_warned:
                self._outer._quota_warned = True
                log.warning(
                    "Sibyl store at %s bytes -- %.1f%% of the free-tier cap",
                    f"{status['db_size_bytes']:,}", 100 * status["pct_used"],
                )
            return self

        def __exit__(self, exc_type, exc, tb):
            if exc_type is CapExceededError:
                raise SibylQuotaExceededError(str(exc)) from exc
            return False

    def _quota_guard(self) -> "_QuotaGuard":
        return PatientMemory._QuotaGuard(self)


def known_patient_ids() -> list[str]:
    """Every patient tenant present in the store, excluding reserved ones.

    Reads tenant ids straight from the entities table. Sibyl's SDK exposes no
    "list tenants" call -- it is designed around knowing which tenant you want
    -- so this is the one place MEMORA touches the underlying SQLite directly,
    read-only, rather than inventing a parallel registry that could drift out of
    step with what is actually stored.
    """
    import sqlite3

    from memora.sentinel.digest import SENTINEL_SYSTEM_ID

    db_path = settings.sibyl_db_path
    assert_store_available(db_path)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT DISTINCT tenant_id FROM entities").fetchall()
    finally:
        con.close()

    prefix = "patient-"
    ids = [r[0][len(prefix):] for r in rows if r[0].startswith(prefix)]
    return sorted(i for i in ids if i != SENTINEL_SYSTEM_ID)


def patient_summary(patient_id: str) -> dict:
    """Enough about one patient to choose them from a list, without loading
    their whole record.

    Exists because the frontend previously had no way to discover who was in
    the store at all, and shipped a hardcoded fixture id that may not be
    present in whatever Sibyl store the API is pointed at. Real ids are
    Synthea UUIDs generated per ingestion run -- they cannot be known ahead
    of time, so they have to be asked for.
    """
    from memora.ontology.kinds import ALL_KINDS

    memory = PatientMemory(patient_id)
    kinds: dict[str, int] = {}
    has_drug_allergy = False
    latest = ""

    for kind in ALL_KINDS:
        rows = memory.list_facts(kind)
        if rows:
            kinds[kind] = len(rows)
        for row in rows:
            if isinstance(row.get("body"), dict) and row["body"].get("is_drug_allergy"):
                has_drug_allergy = True
            if row.get("updated_at", "") > latest:
                latest = row["updated_at"]

    return {
        "patient_id": patient_id,
        "fact_count": sum(kinds.values()),
        "event_count": len(memory.read_history()),
        "memory_version": memory.memory_version(),
        "kinds": kinds,
        "has_drug_allergy": has_drug_allergy,
        "last_updated": latest or None,
    }


def full_memory(patient_id: str, event_limit: int = 200) -> dict:
    """Everything Sibyl holds for one patient, shaped for inspection.

    Deliberately distinct from the Context Engine's retrieval: execute_plan
    answers "what matters for THIS situation", which is a filtered, ranked,
    capped view. This answers "what is actually stored", unfiltered, so the
    memory layer can be looked at directly rather than only through the lens
    of a clinical question.

    That distinction is the point. A claim that memory is real is worth less
    than the ability to open it.
    """
    from memora.ontology.events import ClinicalEvent
    from memora.ontology.kinds import ALL_KINDS

    memory = PatientMemory(patient_id, require_data=True)

    facts: dict[str, list[dict]] = {}
    trends: list[dict] = []
    for kind in ALL_KINDS:
        rows = memory.list_facts(kind)
        if not rows:
            continue
        rows.sort(key=lambda r: r["name"])
        facts[kind] = rows
        for row in rows:
            body = row.get("body")
            if isinstance(body, dict) and body.get("series"):
                trends.append({
                    "name": row["name"],
                    "test": body.get("test"),
                    "loinc": body.get("loinc"),
                    "unit": body.get("unit"),
                    "direction": body.get("direction"),
                    "delta": body.get("delta"),
                    "readings": body.get("readings"),
                    "latest_value": body.get("latest_value"),
                    "latest_at": body.get("latest_at"),
                    "series": body.get("series"),
                })

    # Trajectories first -- a five-point series says more than a single value.
    trends.sort(key=lambda t: -(t.get("readings") or 0))

    history = memory.read_history(limit=event_limit)
    events = []
    for record in history:
        event = ClinicalEvent.from_record(record)
        events.append({
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "summary": event.summary,
            "severity": event.severity,
            "related_kind": event.related_kind,
            "related_name": event.related_name,
            "source_id": event.source_id,
        })
    events.sort(key=lambda e: e["timestamp"], reverse=True)

    quota = memory.quota()
    return {
        "patient_id": patient_id,
        "memory_version": memory.memory_version(),
        "fact_count": sum(len(v) for v in facts.values()),
        "event_count": len(events),
        "facts": facts,
        "trends": trends,
        "events": events,
        "active_situation": memory.get_context("active_situation"),
        "memory": {
            "db_size_bytes": quota["db_size_bytes"],
            "soft_cap_bytes": quota["soft_cap_bytes"],
            "pct_used": quota.get("pct_used"),
        },
    }