"""Clinician sessions and question threads, persisted in Sibyl.

A session is a clinician working on one patient. It holds threads; a thread
holds the questions asked in it. Both are WARM entities rather than journal
events, because both have lifecycle (open -> closed) and both must be
enumerable -- `list_facts(KIND_SESSION)` is a real query, and a session that
could only be found by scanning the journal would not survive a restart in any
useful way.

Nothing here is UI state. A "New thread" button that only cleared the screen
would prove nothing about memory; these records outlive the process that wrote
them, which is the entire point.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from memora.sessions.runtime import BOOT_ID
from memora.sibyl.client import PatientMemory

KIND_SESSION = "session"
KIND_THREAD = "thread"

STATUS_OPEN = "open"
STATUS_CLOSED = "closed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _short() -> str:
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def open_session(memory: PatientMemory, clinician_id: str,
                 clinician_name: str | None = None) -> dict:
    """Start a session and record which process started it."""
    session_id = f"s_{_short()}"
    body = {
        "session_id": session_id,
        "clinician_id": clinician_id,
        "clinician_name": clinician_name or clinician_id,
        "patient_id": memory.scope.patient_id,
        "started_at": _now(),
        "ended_at": None,
        "boot_id": BOOT_ID,
        "threads": [],
        "questions_asked": 0,
        "decisions": [],
    }
    memory.set_fact(KIND_SESSION, session_id, body, status=STATUS_OPEN)
    return body


def get_session(memory: PatientMemory, session_id: str) -> dict | None:
    return memory.get_fact_body(KIND_SESSION, session_id)


def list_sessions(memory: PatientMemory, limit: int = 100) -> list[dict]:
    """Every session for this patient, newest first."""
    rows = memory.list_facts(KIND_SESSION, limit=limit)
    bodies = [r["body"] for r in rows if isinstance(r.get("body"), dict)]
    return sorted(bodies, key=lambda b: b.get("started_at") or "", reverse=True)


def close_session(memory: PatientMemory, session_id: str) -> dict | None:
    body = get_session(memory, session_id)
    if body is None:
        return None
    body["ended_at"] = _now()
    memory.set_fact(KIND_SESSION, session_id, body, status=STATUS_CLOSED)
    return body


def _touch_session(memory: PatientMemory, session_id: str, **changes) -> dict | None:
    """Merge changes into a stored session without clobbering the rest of it."""
    body = get_session(memory, session_id)
    if body is None:
        return None
    body.update(changes)
    memory.set_fact(KIND_SESSION, session_id, body,
                    status=STATUS_CLOSED if body.get("ended_at") else STATUS_OPEN)
    return body


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

def open_thread(memory: PatientMemory, session_id: str,
                title: str | None = None) -> dict | None:
    session = get_session(memory, session_id)
    if session is None:
        return None

    thread_id = f"t_{_short()}"
    body = {
        "thread_id": thread_id,
        "session_id": session_id,
        "patient_id": memory.scope.patient_id,
        "clinician_id": session.get("clinician_id"),
        "title": title,
        "opened_at": _now(),
        "boot_id": BOOT_ID,
        "questions": [],
    }
    memory.set_fact(KIND_THREAD, thread_id, body, status=STATUS_OPEN)

    threads = list(session.get("threads") or [])
    threads.append(thread_id)
    _touch_session(memory, session_id, threads=threads)
    return body


def get_thread(memory: PatientMemory, thread_id: str) -> dict | None:
    return memory.get_fact_body(KIND_THREAD, thread_id)


def list_threads(memory: PatientMemory, session_id: str | None = None,
                 limit: int = 200) -> list[dict]:
    rows = memory.list_facts(KIND_THREAD, limit=limit)
    bodies = [r["body"] for r in rows if isinstance(r.get("body"), dict)]
    if session_id:
        bodies = [b for b in bodies if b.get("session_id") == session_id]
    return sorted(bodies, key=lambda b: b.get("opened_at") or "", reverse=True)


def record_question(memory: PatientMemory, thread_id: str, *, question: str,
                    answered: bool, answer: str, verdicts: dict[str, int],
                    matched: int) -> dict | None:
    """Append one asked question to its thread, and count it on the session.

    What is stored is the SHAPE of the outcome -- was it answered, what did the
    gate decide, how many records were matched -- not the prose. A later
    session recalls that this question was asked and how it resolved, which is
    what changes a decision; replaying old prose would just be a transcript.
    """
    thread = get_thread(memory, thread_id)
    if thread is None:
        return None

    entry = {
        "question": question,
        "asked_at": _now(),
        "answered": answered,
        "answer_preview": (answer or "")[:280],
        "verdicts": verdicts,
        "records_matched": matched,
        "boot_id": BOOT_ID,
    }
    questions = list(thread.get("questions") or [])
    questions.append(entry)
    thread["questions"] = questions
    memory.set_fact(KIND_THREAD, thread_id, thread, status=STATUS_OPEN)

    session_id = thread.get("session_id")
    if session_id:
        session = get_session(memory, session_id)
        if session is not None:
            _touch_session(memory, session_id,
                           questions_asked=int(session.get("questions_asked") or 0) + 1)
    return entry


def record_decision(memory: PatientMemory, session_id: str, *, kind: str,
                    detail: str) -> dict | None:
    """Note a consequential act -- an approved handover, a documented reaction."""
    session = get_session(memory, session_id)
    if session is None:
        return None
    decisions = list(session.get("decisions") or [])
    decisions.append({"kind": kind, "detail": detail, "at": _now(), "boot_id": BOOT_ID})
    return _touch_session(memory, session_id, decisions=decisions)
