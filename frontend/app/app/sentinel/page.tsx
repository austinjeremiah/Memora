"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getPatientMemory, listPatients, recordEvent, runSentinel } from "@/lib/api/client";
import {
  AutonomousCheckOut, FindingOut, MemoraApiError, PatientMemoryOut,
  PatientSummaryOut, SentinelRunOut, Situation,
} from "@/lib/api/types";
import { SITUATIONS } from "@/lib/config/demo-data";
import DriftGraph from "@/components/app/DriftGraph";
import {
  Badge, Button, Card, EmptyState, Field, Mono, Notice, Section,
  SkeletonList, StatTile,
} from "@/components/app/ui";

/**
 * Sentinel — the proactive path.
 *
 * No model is involved anywhere in this page's data. Findings are built
 * directly from persisted records and judged by the same Gate the reactive
 * path uses, so "the model can be wrong, the gate can't" holds for an entire
 * mode of the system with no model present to be wrong.
 */
export default function SentinelPage() {
  const [situation, setSituation] = useState<Situation>("icu_to_ward");
  const [run, setRun] = useState<SentinelRunOut | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<MemoraApiError | null>(null);
  const [history, setHistory] = useState<SentinelRunOut[]>([]);

  const sweep = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await runSentinel({ situation });
      setRun(res);
      setHistory((h) => [...h, res].slice(-4));
    } catch (e) {
      setError(e as MemoraApiError);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="stack stack--loose">
      <div className="stack stack--tight">
        <h1 className="page-title">Sentinel</h1>
        <p className="subtle" style={{ margin: 0, maxWidth: 680 }}>
          Watches memory for facts that contradict their own history — a
          medication recorded as active while the journal holds a documented
          reaction to it. Both sides came from the same store, so they cannot
          both be right.
        </p>
        <div><Badge tone="accent">no model runs in this path</Badge></div>
      </div>

      <Card>
        <div className="stack">
          <Field label="Situation"
                 hint="Decides which record kinds are swept, using the same focus table as retrieval">
            <select className="select" value={situation}
                    onChange={(e) => setSituation(e.target.value as Situation)}>
              {SITUATIONS.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </Field>
          <div className="row">
            <Button variant="primary" onClick={() => void sweep()} disabled={running}>
              {running ? "Sweeping…" : run ? "Sweep again" : "Run a sweep"}
            </Button>
            {run && (
              <span className="dim">
                run {history.length} · {run.patients_scanned} patients,{" "}
                {run.records_checked} records checked
              </span>
            )}
          </div>
        </div>
      </Card>

      {error && (
        <Notice tone="error"
                title={error.code === "sibyl_unavailable"
                  ? "MEMORA cannot reach its memory layer"
                  : "Sweep failed"}>
          {error.detail}
        </Notice>
      )}

      {running && !run && <SkeletonList rows={3} />}

      {run && (
        <>
          <div className="grid grid--3">
            <StatTile label="Records checked" value={run.records_checked}
                      hint={`${run.patients_scanned} patients`} />
            <StatTile label="Findings" value={run.findings.length}
                      hint="tracked in Sentinel's own digest" />
            <StatTile label="Announceable" value={run.announceable.length}
                      hint="PERSISTING is tracked but never re-alerts" />
          </div>

          {run.findings.length === 0 ? (
            <EmptyState title="No contradictions found">
              Memory is self-consistent across every record checked. Synthea
              never prescribes a drug a patient is allergic to, so a freshly
              ingested store has no drift to find.
            </EmptyState>
          ) : (
            <Section title="Findings">
              <div className="stack">
                {run.findings.map((f) => (
                  <FindingCard key={`${f.patient_id}-${f.kind}-${f.name}`} finding={f} />
                ))}
              </div>
            </Section>
          )}

          {/* Always available. This used to live inside the no-drift empty
              state, so the moment ANY patient had a finding the only way to
              document a reaction disappeared -- and the sweep is global across
              all three patients, so one finding hid the control for every one
              of them. Recording a clinical event is an ordinary operation, not
              something that should be gated on the store being clean. */}
          <DocumentReaction onRecorded={() => void sweep()} />

          {history.length > 1 && (
            <Section title="Across runs">
              <Card>
                <div className="stack stack--tight">
                  {history.map((h, i) => (
                    <div key={i} className="row row--between">
                      <span className="dim">
                        run {i + 1} · {new Date(h.run_at).toLocaleTimeString()}
                      </span>
                      <span className="row" style={{ gap: 6 }}>
                        {Object.entries(h.summary)
                          .filter(([, n]) => n > 0)
                          .map(([status, n]) => (
                            <Badge key={status}
                                   tone={status === "NEW" ? "review"
                                     : status === "RESOLVED" ? "allow"
                                     : status === "ESCALATED" ? "block" : "neutral"}>
                              {n} {status.toLowerCase()}
                            </Badge>
                          ))}
                        {h.announceable.length === 0 && h.findings.length > 0 && (
                          <span className="dim">no re-alert</span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="dim" style={{ marginBottom: 0, marginTop: 10 }}>
                  A finding is announced once. After that it is tracked as
                  PERSISTING and does not alert again — which is what stops a
                  safety system training people to ignore it.
                </p>
              </Card>
            </Section>
          )}
        </>
      )}
    </div>
  );
}

const STATUS_TONE: Record<string, "review" | "allow" | "block" | "neutral"> = {
  NEW: "review", RESOLVED: "allow", ESCALATED: "block", PERSISTING: "neutral",
};

function FindingCard({ finding }: { finding: FindingOut }) {
  return (
    <Card>
      <div className="stack">
        <div className="row row--between" style={{ alignItems: "flex-start" }}>
          <div className="stack stack--tight" style={{ flex: 1, minWidth: 0 }}>
            <span style={{ fontWeight: 600 }}>{finding.reason}</span>
            <div className="row" style={{ gap: 8 }}>
              <Mono truncate={30}>{`${finding.kind}/${finding.name}`}</Mono>
              <Link href={`/app/patients/${encodeURIComponent(finding.patient_id)}`}
                    className="dim" style={{ textDecoration: "none" }}>
                {finding.patient_id.slice(0, 8)}… ↗
              </Link>
            </div>
          </div>
          <Badge tone={STATUS_TONE[finding.status] ?? "neutral"}>{finding.status}</Badge>
        </div>

        <DriftGraph finding={finding} />

        <div className="row" style={{ gap: 8 }}>
          {finding.triggered_rules.map((r) => (
            <Badge key={r} tone="review">{r.replace(/_/g, " ")}</Badge>
          ))}
          <span className="dim">
            detector: {finding.detector} · seen {finding.runs_seen}×
            {finding.runs_seen > 1 && " · not re-alerted"}
          </span>
        </div>
      </div>
    </Card>
  );
}

/**
 * Document a real adverse reaction and let Sentinel find the contradiction.
 *
 * Synthea never prescribes a drug a patient is allergic to, so a clean store
 * genuinely has no drift. Rather than plant a finding, this records an
 * ordinary clinical event — which is how contradictions arise in practice —
 * and the finding that follows is detected rather than seeded.
 */
function DocumentReaction({ onRecorded }: { onRecorded: () => void }) {
  const [patients, setPatients] = useState<PatientSummaryOut[] | null>(null);
  const [patientId, setPatientId] = useState("");
  const [memory, setMemory] = useState<PatientMemoryOut | null>(null);
  const [medication, setMedication] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [check, setCheck] = useState<AutonomousCheckOut | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    listPatients().then(setPatients).catch(() => undefined);
  }, []);

  useEffect(() => {
    setMedication("");
    setMemory(null);
    if (!patientId) return;
    getPatientMemory(patientId, 1).then(setMemory).catch(() => undefined);
  }, [patientId]);

  const actives = (memory?.facts.medication ?? []).filter((f) => f.status === "active");

  const submit = async () => {
    if (!patientId || !medication) return;
    setBusy(true); setErr(null);
    try {
      const res = await recordEvent(patientId, {
        event_type: "adverse_reaction",
        summary: `Documented adverse reaction to ${medication}`,
        related_kind: "medication",
        related_name: medication,
        severity: "critical",
      });
      setDone(medication);
      setCheck(res.autonomous_check);
      onRecorded();
    } catch (e) {
      setErr((e as MemoraApiError).detail);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section title="Document an adverse reaction">
      <Card>
      <div className="stack">
        <p className="subtle" style={{ margin: 0, maxWidth: 640 }}>
          Record a reaction to a medication the store still holds as active.
          That is how contradictions arise in practice, and the finding that
          follows is <em>detected</em> by Sentinel rather than planted.
        </p>

        {err && <Notice tone="error" title="Could not record">{err}</Notice>}
        {done && (
          <Notice tone="warn" title="Recorded — and the agent checked on its own">
            An adverse reaction to <strong>{done}</strong> is now in the journal
            while the medication is still recorded as active.
            {check?.ran && (
              <div className="stack stack--tight" style={{ marginTop: 10 }}>
                <span>
                  Nobody asked for a check. Sentinel swept{" "}
                  <strong>{check.records_checked} records</strong> the moment the
                  information arrived and found{" "}
                  <strong>{check.findings.length}</strong>.
                </span>
                {check.actions_taken.map((a) => (
                  <span key={a.event_id}>
                    It also <strong>wrote into the patient&apos;s record</strong>:{" "}
                    {a.kind}/{a.name} has conflicted across {a.runs_seen} checks.
                    That threshold exists only in the agent&apos;s own memory —
                    without it there is nothing to escalate.
                  </span>
                ))}
              </div>
            )}
          </Notice>
        )}

        <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
          <div style={{ minWidth: 220 }}>
            <Field label="Patient">
              <select className="select" value={patientId}
                      onChange={(e) => setPatientId(e.target.value)}>
                <option value="">Select…</option>
                {patients?.map((p) => (
                  <option key={p.patient_id} value={p.patient_id}>
                    {p.patient_id.slice(0, 8)}…
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div style={{ minWidth: 260 }}>
            <Field label="Active medication">
              <select className="select" value={medication} disabled={!actives.length}
                      onChange={(e) => setMedication(e.target.value)}>
                <option value="">
                  {patientId ? (actives.length ? "Select…" : "none active") : "pick a patient"}
                </option>
                {actives.map((f) => (
                  <option key={f.name} value={f.name}>{f.name.slice(0, 40)}</option>
                ))}
              </select>
            </Field>
          </div>
          <Button variant="primary" onClick={() => void submit()}
                  disabled={busy || !medication}>
            {busy ? "Recording…" : "Document a reaction"}
          </Button>
        </div>
      </div>
      </Card>
    </Section>
  );
}
