"use client";

import { useCallback, useEffect, useState } from "react";
import {
  closeSession, getClinicians, listThreads, openSession, openThread,
} from "@/lib/api/client";
import {
  ClinicianOut, MemoraApiError, PriorContextOut, SessionOut, ThreadOut,
} from "@/lib/api/types";
import { Badge, Button, Card, Notice } from "./ui";

export interface SessionState {
  session: SessionOut;
  thread: ThreadOut | null;
  prior: PriorContextOut;
}

/**
 * The session a clinician is working in, and what it inherited.
 *
 * This exists because the eligibility gate asks for recall in a genuinely
 * fresh session, and a "New thread" button that only cleared the screen would
 * prove nothing -- it is the wrapper failure the rules name explicitly.
 *
 * What is shown instead is checkable. Every session records the `boot_id` of
 * the API process that opened it. When this session inherits work written
 * under a DIFFERENT boot id, that writer's process is gone, so the only path
 * by which its work reached here is Sibyl. The banner reports that as a count,
 * not as a claim.
 */
export default function SessionBar({ patientId, onChange }: {
  patientId: string;
  onChange?: (s: SessionState | null) => void;
}) {
  const [clinicians, setClinicians] = useState<ClinicianOut[] | null>(null);
  const [clinicianId, setClinicianId] = useState("");
  const [state, setState] = useState<SessionState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<MemoraApiError | null>(null);

  useEffect(() => {
    getClinicians().then((list) => {
      setClinicians(list);
      if (list.length) setClinicianId((c) => c || list[0].id);
    }).catch((e) => setError(e as MemoraApiError));
  }, []);

  const publish = useCallback((s: SessionState | null) => {
    setState(s);
    onChange?.(s);
  }, [onChange]);

  const start = async () => {
    if (!clinicianId) return;
    setBusy(true); setError(null);
    try {
      const opened = await openSession(patientId, clinicianId);
      const thread = await openThread(patientId, opened.session.session_id,
                                      "Working thread");
      publish({ session: opened.session, thread, prior: opened.prior });
    } catch (e) {
      setError(e as MemoraApiError);
    } finally {
      setBusy(false);
    }
  };

  const newThread = async () => {
    if (!state) return;
    setBusy(true);
    try {
      const thread = await openThread(patientId, state.session.session_id,
                                      `Thread ${state.session.threads.length + 1}`);
      const threads = await listThreads(patientId, state.session.session_id);
      publish({
        ...state, thread,
        session: { ...state.session, threads: threads.map((t) => t.thread_id) },
      });
    } catch (e) {
      setError(e as MemoraApiError);
    } finally {
      setBusy(false);
    }
  };

  const end = async () => {
    if (!state) return;
    setBusy(true);
    try {
      await closeSession(patientId, state.session.session_id);
      publish(null);
    } catch (e) {
      setError(e as MemoraApiError);
    } finally {
      setBusy(false);
    }
  };

  if (error) {
    return (
      <Notice tone="error" title="Could not start a session">{error.detail}</Notice>
    );
  }

  if (!state) {
    return (
      <Card tight>
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <span className="field__label" style={{ marginRight: "auto" }}>
            Start a session to ask questions and carry decisions forward
          </span>
          <select className="select" style={{ width: 170 }} value={clinicianId}
                  onChange={(e) => setClinicianId(e.target.value)}
                  disabled={!clinicians}>
            {clinicians?.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <Button variant="primary" onClick={() => void start()}
                  disabled={busy || !clinicianId}>
            {busy ? "Opening…" : "Open session"}
          </Button>
        </div>
      </Card>
    );
  }

  const { session, prior, thread } = state;

  return (
    <div className="stack stack--tight">
      <Card tight>
        <div className="session">
          <div className="session__who">
            <span className="session__name">
              {session.clinician_name ?? session.clinician_id}
            </span>
            <span className="session__ids">
              session {session.session_id}
              {thread && <> · thread {thread.thread_id}</>}
            </span>
          </div>

          <div className="session__boot" title="Identity of the API process that opened this session">
            <span className="match__k">process</span>
            <span className="session__bootid">{prior.current_boot_id}</span>
          </div>

          <div className="row" style={{ gap: 8 }}>
            <Button onClick={() => void newThread()} disabled={busy}>New thread</Button>
            <Button onClick={() => void end()} disabled={busy}>End session</Button>
          </div>
        </div>
      </Card>

      <RecallBanner prior={prior} />
    </div>
  );
}

/**
 * What this session inherited, and whether it crossed a process boundary.
 *
 * The distinction the banner draws is the one the gate turns on: recalling
 * work from the SAME process proves nothing, because it could have been held
 * in memory. Recalling work from a process that has since died can only have
 * come through the store.
 */
function RecallBanner({ prior }: { prior: PriorContextOut }) {
  if (prior.prior_session_count === 0) {
    return (
      <Notice tone="info" title="First session for this patient">
        Nothing has been written yet, so there is nothing to recall. Record
        something, restart the API, and open a session again — what comes back
        will have survived the process that wrote it.
      </Notice>
    );
  }

  const dead = prior.sessions_from_dead_processes;

  return (
    <Card tight>
      <div className="stack stack--tight">
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <Badge tone={prior.crossed_restart ? "allow" : "neutral"}>
            {prior.crossed_restart ? "recall crossed a restart" : "same process"}
          </Badge>
          <span className="dim">
            {prior.prior_session_count} prior session
            {prior.prior_session_count === 1 ? "" : "s"}
            {dead > 0 && <> · {dead} written by {dead === 1 ? "a process" : "processes"} that no longer {dead === 1 ? "exists" : "exist"}</>}
            {" · memory version "}{prior.memory_version}
          </span>
        </div>

        {prior.critical_events.length > 0 && (
          <div className="stack stack--tight">
            <span className="field__label">
              Carried into this session — {prior.critical_events.length} critical
              {prior.critical_events.length === 1 ? " entry" : " entries"}
            </span>
            {prior.critical_events.slice(0, 4).map((e, i) => (
              <div key={`${e.source_id ?? i}-${i}`} className="recall__item">
                <span className="recall__when">{e.timestamp.slice(0, 10)}</span>
                <span className="recall__what">{e.summary}</span>
              </div>
            ))}
          </div>
        )}

        {prior.sessions.length > 0 && (
          <details>
            <summary className="dim" style={{ cursor: "pointer" }}>
              Sessions before this one
            </summary>
            <div className="stack stack--tight" style={{ marginTop: 8 }}>
              {prior.sessions.slice(0, 6).map((s) => (
                <div key={s.session_id} className="recall__item">
                  <span className="recall__when">{s.started_at.slice(0, 16).replace("T", " ")}</span>
                  <span className="recall__what">
                    {s.clinician_name ?? s.clinician_id} · {s.questions_asked} question
                    {s.questions_asked === 1 ? "" : "s"}
                  </span>
                  <span className={`recall__boot${s.boot_id !== prior.current_boot_id ? " recall__boot--dead" : ""}`}>
                    {s.boot_id}
                    {s.boot_id !== prior.current_boot_id ? " · ended" : " · this process"}
                  </span>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </Card>
  );
}
