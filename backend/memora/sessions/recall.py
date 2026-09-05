"""What a fresh session inherits from the sessions before it.

This is the module the eligibility gate is actually about. A session opening
here does not begin from nothing: it reads what earlier sessions asked,
decided and recorded, and reports which of that was written by a process that
no longer exists.

The `crossed_restart` flag is the load-bearing detail. It is true when a prior
session carries a different `boot_id` from the running process, which means the
process that wrote it has been gone since -- so nothing recalled could have
been held in RAM, and Sibyl is the only path by which it survived.
"""

from __future__ import annotations

from memora.ontology.events import SEVERITY_CRITICAL
from memora.sessions.runtime import BOOT_ID
from memora.sessions.store import list_sessions, list_threads
from memora.sibyl.client import PatientMemory


def prior_context(memory: PatientMemory, *, exclude_session_id: str | None = None,
                  event_limit: int = 200) -> dict:
    """Everything a newly-opened session should know before it answers anything."""
    sessions = [s for s in list_sessions(memory)
                if s.get("session_id") != exclude_session_id]
    threads = [t for t in list_threads(memory)
               if t.get("session_id") != exclude_session_id]

    foreign = [s for s in sessions if s.get("boot_id") and s["boot_id"] != BOOT_ID]

    questions: list[dict] = []
    for t in threads:
        for q in (t.get("questions") or []):
            questions.append({**q, "thread_id": t.get("thread_id"),
                              "session_id": t.get("session_id"),
                              "clinician_id": t.get("clinician_id")})
    questions.sort(key=lambda q: q.get("asked_at") or "", reverse=True)

    decisions: list[dict] = []
    for s in sessions:
        for d in (s.get("decisions") or []):
            decisions.append({**d, "session_id": s.get("session_id"),
                              "clinician_id": s.get("clinician_id")})
    decisions.sort(key=lambda d: d.get("at") or "", reverse=True)

    # Critical journal entries are what actually change a later decision --
    # a documented reaction outranks the fact that someone asked a question.
    history = memory.read_history(limit=event_limit)
    critical = [e for e in history
                if (e.get("extra") or {}).get("severity") == SEVERITY_CRITICAL]

    return {
        "current_boot_id": BOOT_ID,
        "sessions": sessions,
        "prior_session_count": len(sessions),
        "sessions_from_dead_processes": len(foreign),
        "crossed_restart": bool(foreign),
        "questions": questions,
        "decisions": decisions,
        "critical_events": [_event_out(e) for e in critical[:20]],
        "memory_version": memory.memory_version(),
    }


def _event_out(row: dict) -> dict:
    extra = row.get("extra") or {}
    return {
        "timestamp": row.get("ts") or extra.get("timestamp") or "",
        "summary": (row.get("acted") or [""])[0],
        "event_type": extra.get("event_type"),
        "severity": extra.get("severity"),
        "related_kind": extra.get("related_kind"),
        "related_name": extra.get("related_name"),
        "source_id": extra.get("source_id"),
    }
