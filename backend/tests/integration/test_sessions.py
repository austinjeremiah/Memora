"""Sessions, threads, and recall across a process boundary.

The hackathon's eligibility gate asks for three things: persist context that
matters, recall it in a genuinely fresh session, and use it to change a
decision. These tests assert all three, and the middle one is asserted the only
way it can honestly be: by faking a different process identity, since a test
runs in one interpreter.

`test_recall_survives_a_real_process_restart` is the exception -- it spawns an
actual subprocess, so nothing it reads could have been resident in this
process's memory.
"""

import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from memora.api.schemas import SessionOut
from memora.main import app
from memora.ontology.kinds import KIND_MEDICATION, STATUS_ACTIVE
from memora.sessions import runtime, store
from memora.sessions.recall import prior_context
from memora.sessions.store import (
    list_sessions,
    list_threads,
    open_session,
    open_thread,
    record_question,
)
from memora.sibyl.client import PatientMemory

pytestmark = pytest.mark.integration

PATIENT = "P-SESSION"


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def seeded(store):
    """A patient with one active medication, in a real empty store."""
    m = PatientMemory(PATIENT)
    m.set_fact(KIND_MEDICATION, "naproxen", {"label": "Naproxen"}, status=STATUS_ACTIVE)
    return m


# ---- the records themselves --------------------------------------------

def test_a_session_records_the_process_that_opened_it(seeded):
    s = open_session(seeded, "dr_maya", "Dr. Maya")
    assert s["boot_id"] == runtime.BOOT_ID
    assert s["clinician_id"] == "dr_maya"
    assert s["ended_at"] is None


def test_sessions_survive_being_re_read_from_the_store(seeded):
    s = open_session(seeded, "dr_maya")
    fresh = PatientMemory(PATIENT)
    found = [x for x in list_sessions(fresh) if x["session_id"] == s["session_id"]]
    assert len(found) == 1, "a session must be readable by any client, not just its writer"


def test_a_thread_belongs_to_its_session(seeded):
    s = open_session(seeded, "dr_maya")
    t = open_thread(seeded, s["session_id"])
    assert t["session_id"] == s["session_id"]
    assert store.get_session(seeded, s["session_id"])["threads"] == [t["thread_id"]]


def test_opening_a_thread_on_an_unknown_session_returns_none(seeded):
    assert open_thread(seeded, "s_doesnotexist") is None


def test_questions_accumulate_on_the_thread_and_count_on_the_session(seeded):
    s = open_session(seeded, "dr_maya")
    t = open_thread(seeded, s["session_id"])
    for q in ("Is renal function stable?", "Can I restart naproxen?"):
        record_question(seeded, t["thread_id"], question=q, answered=True,
                        answer="…", verdicts={"ALLOW": 1}, matched=3)

    stored = store.get_thread(seeded, t["thread_id"])
    assert [q["question"] for q in stored["questions"]] == [
        "Is renal function stable?", "Can I restart naproxen?"]
    assert store.get_session(seeded, s["session_id"])["questions_asked"] == 2


# ---- recall -------------------------------------------------------------

def test_a_session_does_not_recall_itself(seeded):
    s = open_session(seeded, "dr_maya")
    prior = prior_context(seeded, exclude_session_id=s["session_id"])
    assert all(x["session_id"] != s["session_id"] for x in prior["sessions"])


def test_recall_reports_no_restart_when_everything_is_this_process(seeded):
    open_session(seeded, "dr_maya")
    prior = prior_context(seeded)
    assert prior["crossed_restart"] is False
    assert prior["sessions_from_dead_processes"] == 0


def test_recall_detects_a_session_written_by_a_dead_process(seeded, monkeypatch):
    """The gate's evidence. A differing boot_id means that writer is gone."""
    monkeypatch.setattr(runtime, "BOOT_ID", "deadbeefcafe")
    monkeypatch.setattr(store, "BOOT_ID", "deadbeefcafe")
    open_session(seeded, "dr_maya")

    monkeypatch.undo()  # back to this process's real identity
    prior = prior_context(seeded)
    assert prior["crossed_restart"] is True
    assert prior["sessions_from_dead_processes"] >= 1
    assert prior["current_boot_id"] == runtime.BOOT_ID


def test_recall_surfaces_critical_events_over_routine_ones(seeded):
    from memora.ontology.events import SEVERITY_CRITICAL, ClinicalEvent

    seeded.log_event(ClinicalEvent(
        event_type="adverse_reaction",
        summary="Urticaria after naproxen.",
        timestamp="2026-04-25T10:00:00+00:00",
        related_kind=KIND_MEDICATION, related_name="naproxen",
        source_id="test-reaction", severity=SEVERITY_CRITICAL))

    prior = prior_context(seeded)
    assert any("naproxen" in e["summary"].lower() for e in prior["critical_events"])


# ---- the API ------------------------------------------------------------

def test_opening_a_session_returns_what_it_inherited(client, seeded):
    r = client.post(f"/patients/{PATIENT}/sessions", json={"clinician_id": "dr_maya"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert SessionOut(**body["session"]).clinician_id == "dr_maya"
    assert body["prior"]["current_boot_id"] == runtime.BOOT_ID


def test_an_unknown_clinician_cannot_open_a_session(client, seeded):
    r = client.post(f"/patients/{PATIENT}/sessions", json={"clinician_id": "nobody"})
    assert r.status_code == 400


def test_runtime_reports_a_stable_boot_id(client):
    a = client.get("/runtime").json()
    b = client.get("/runtime").json()
    assert a["boot_id"] == b["boot_id"] == runtime.BOOT_ID


def test_threads_can_be_filtered_to_one_session(client, seeded):
    s1 = open_session(seeded, "dr_maya")
    s2 = open_session(seeded, "dr_arun")
    open_thread(seeded, s1["session_id"])
    open_thread(seeded, s2["session_id"])

    only = client.get(f"/patients/{PATIENT}/threads?session_id={s1['session_id']}").json()
    assert len(only) == 1
    assert only[0]["session_id"] == s1["session_id"]
    assert len(list_threads(seeded)) >= 2


# ---- the real thing -----------------------------------------------------

def test_recall_survives_a_real_process_restart(seeded, store):
    """Write here, read from a genuinely separate interpreter.

    Nothing asserted by the subprocess could have come from this process's
    memory, so a pass means Sibyl is the only path the session survived by.
    """
    s = open_session(seeded, "dr_maya", "Dr. Maya")

    script = f"""
import json
from memora.sibyl.client import PatientMemory
from memora.sessions.recall import prior_context
from memora.sessions.runtime import BOOT_ID

prior = prior_context(PatientMemory({PATIENT!r}))
print(json.dumps({{
    "boot": BOOT_ID,
    "found": [x["session_id"] for x in prior["sessions"]],
    "crossed": prior["crossed_restart"],
    "dead": prior["sessions_from_dead_processes"],
}}))
"""
    # settings is monkeypatched in THIS process only, so the store path has to
    # travel to the subprocess the way a real deployment passes it: the env.
    env = {**os.environ, "SIBYL_DB_PATH": str(store)}
    out = subprocess.run([sys.executable, "-c", script], capture_output=True,
                         text=True, timeout=120, env=env)
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout.strip().splitlines()[-1])

    assert result["boot"] != runtime.BOOT_ID, "the subprocess must be a different process"
    assert s["session_id"] in result["found"], "the session did not survive the restart"
    assert result["crossed"] is True
    assert result["dead"] >= 1

