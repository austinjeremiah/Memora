"use client";

import { useEffect, useMemo, useState } from "react";
import { getClinicians, requestHandoff } from "@/lib/api/client";
import { useAppStatus } from "@/lib/api/AppStatusContext";
import { ClinicianOut, HandoffOut, Situation } from "@/lib/api/types";
import { SITUATIONS } from "@/lib/config/demo-data";
import PatientPicker from "@/components/app/PatientPicker";
import {
  ClaimsList,
  ClaimsSummaryBadges,
  LOADING_MESSAGES,
  errorMessage,
  primaryBtn,
} from "@/app/app/_components/claimDisplay";
import SibylWarningBanner from "@/app/app/_components/SibylWarningBanner";

type ColumnState =
  | { status: "idle" }
  | { status: "loading"; messageIndex: number }
  | { status: "loaded"; response: HandoffOut }
  | { status: "error"; error: { heading: string; body: string } };

function Column({ label, state }: { label: string; state: ColumnState }) {
  return (
    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: "14px" }}>
      <h3 style={{ margin: 0, opacity: 0.7, fontSize: "14px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </h3>

      {state.status === "idle" && <p style={{ opacity: 0.5, fontSize: "14px" }}>Not run yet.</p>}

      {state.status === "loading" && (
        <p style={{ opacity: 0.75, fontSize: "14px" }}>{LOADING_MESSAGES[state.messageIndex]}</p>
      )}

      {state.status === "error" && (
        <div style={{ border: "1px solid #ff6b6b", borderRadius: "10px", padding: "14px 16px" }}>
          <p style={{ margin: "0 0 4px 0", color: "#ff6b6b", fontWeight: 600, fontSize: "14px" }}>
            {state.error.heading}
          </p>
          <p style={{ margin: 0, fontSize: "13px", opacity: 0.85 }}>{state.error.body}</p>
        </div>
      )}

      {state.status === "loaded" && (
        <>
          <p style={{ margin: 0, fontSize: "13px", opacity: 0.6 }}>
            Task: {state.response.task} · {state.response.proposed_count} claim(s) proposed
          </p>
          <ClaimsSummaryBadges claims={state.response.claims} />
          <ClaimsList claims={state.response.claims} />
        </>
      )}
    </div>
  );
}

export default function ComparePage() {
  const { reportMemory } = useAppStatus();

  const [patientId, setPatientId] = useState("");
  const [clinicianId, setClinicianId] = useState("");
  const [situationA, setSituationA] = useState<Situation | "">("");
  const [situationB, setSituationB] = useState<Situation | "">("");

  const [clinicians, setClinicians] = useState<ClinicianOut[] | null>(null);
  const [clinicianError, setClinicianError] = useState<string | null>(null);

  const [colA, setColA] = useState<ColumnState>({ status: "idle" });
  const [colB, setColB] = useState<ColumnState>({ status: "idle" });

  useEffect(() => {
    let cancelled = false;
    getClinicians()
      .then((list) => !cancelled && setClinicians(list))
      .catch((e) => !cancelled && setClinicianError(e instanceof Error ? e.message : "Could not load clinicians."));
    return () => {
      cancelled = true;
    };
  }, []);

  // Independent cycling loading-message timers per column.
  useEffect(() => {
    if (colA.status !== "loading") return;
    const id = setInterval(() => {
      setColA((s) => (s.status === "loading" ? { status: "loading", messageIndex: (s.messageIndex + 1) % LOADING_MESSAGES.length } : s));
    }, 1700);
    return () => clearInterval(id);
  }, [colA.status]);

  useEffect(() => {
    if (colB.status !== "loading") return;
    const id = setInterval(() => {
      setColB((s) => (s.status === "loading" ? { status: "loading", messageIndex: (s.messageIndex + 1) % LOADING_MESSAGES.length } : s));
    }, 1700);
    return () => clearInterval(id);
  }, [colB.status]);

  const sameSituationTwice = situationA !== "" && situationA === situationB;
  const canCompare = Boolean(patientId && clinicianId && situationA && situationB) && !sameSituationTwice;

  const runColumn = (situation: Situation, setState: (s: ColumnState) => void) => {
    setState({ status: "loading", messageIndex: 0 });
    requestHandoff({ patient_id: patientId, situation, clinician_id: clinicianId })
      .then((res) => {
        setState({ status: "loaded", response: res });
        reportMemory(res.memory);
      })
      .catch((e) => setState({ status: "error", error: errorMessage(e) }));
  };

  const compare = () => {
    if (!canCompare) return;
    // Both requests run concurrently and are handled independently — one
    // side failing must not block or hide the other's result (§8.1).
    runColumn(situationA as Situation, setColA);
    runColumn(situationB as Situation, setColB);
  };

  const diffSummary = useMemo(() => {
    if (colA.status !== "loaded" || colB.status !== "loaded") return null;
    const textsA = new Set(colA.response.claims.map((c) => c.text));
    const textsB = new Set(colB.response.claims.map((c) => c.text));
    let both = 0;
    for (const t of textsA) if (textsB.has(t)) both++;
    return { a: textsA.size, b: textsB.size, both };
  }, [colA, colB]);

  const situationLabel = (v: Situation | "") => SITUATIONS.find((s) => s.value === v)?.label ?? "";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <h1 style={{ margin: 0 }}>Compare Situations</h1>
      <SibylWarningBanner />
      <p style={{ margin: 0, opacity: 0.7 }}>
        The same patient&apos;s memory, compared across two situations — two ordinary{" "}
        <code>POST /handoff</code> calls, run side by side.
      </p>

      <section style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1, minWidth: "220px" }}>
            <label htmlFor="cmp-patient" style={{ fontSize: "13px", opacity: 0.7 }}>
              Patient
            </label>
            <PatientPicker value={patientId} onChange={setPatientId} />
                      </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1, minWidth: "220px" }}>
            <label htmlFor="cmp-clinician" style={{ fontSize: "13px", opacity: 0.7 }}>
              Clinician
            </label>
            {clinicianError && <p style={{ margin: 0, fontSize: "13px", color: "#ff6b6b" }}>{clinicianError}</p>}
            {!clinicianError && clinicians === null && <p style={{ margin: 0, fontSize: "13px", opacity: 0.6 }}>Loading...</p>}
            {clinicians !== null && (
              <select id="cmp-clinician" value={clinicianId} onChange={(e) => setClinicianId(e.target.value)} style={selectStyle}>
                <option value="">Select a clinician...</option>
                {clinicians.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} — {c.role}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1, minWidth: "220px" }}>
            <label htmlFor="cmp-situation-a" style={{ fontSize: "13px", opacity: 0.7 }}>
              Situation A
            </label>
            <select
              id="cmp-situation-a"
              value={situationA}
              onChange={(e) => setSituationA(e.target.value as Situation)}
              style={selectStyle}
            >
              <option value="">Select a situation...</option>
              {SITUATIONS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1, minWidth: "220px" }}>
            <label htmlFor="cmp-situation-b" style={{ fontSize: "13px", opacity: 0.7 }}>
              Situation B
            </label>
            <select
              id="cmp-situation-b"
              value={situationB}
              onChange={(e) => setSituationB(e.target.value as Situation)}
              style={selectStyle}
            >
              <option value="">Select a situation...</option>
              {SITUATIONS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {sameSituationTwice && (
          <p style={{ margin: 0, color: "#ffb020", fontSize: "13px" }}>
            Choose two different situations to compare.
          </p>
        )}

        <button
          type="button"
          onClick={compare}
          disabled={!canCompare}
          style={{
            ...primaryBtn,
            alignSelf: "flex-start",
            opacity: canCompare ? 1 : 0.4,
            cursor: canCompare ? "pointer" : "default",
          }}
        >
          Compare
        </button>
      </section>

      {diffSummary && (
        <p
          style={{
            margin: 0,
            padding: "12px 16px",
            border: "1px solid rgba(255,255,255,0.15)",
            borderRadius: "10px",
            fontSize: "14px",
            opacity: 0.85,
          }}
        >
          {situationLabel(situationA)} surfaced {diffSummary.a} claim(s); {situationLabel(situationB)} surfaced{" "}
          {diffSummary.b} claim(s); {diffSummary.both} claim(s) appear in both.
        </p>
      )}

      {(colA.status !== "idle" || colB.status !== "idle") && (
        <div style={{ display: "flex", gap: "28px", flexWrap: "wrap", borderTop: "1px solid rgba(255,255,255,0.15)", paddingTop: "20px" }}>
          <Column label={situationLabel(situationA) || "Situation A"} state={colA} />
          <Column label={situationLabel(situationB) || "Situation B"} state={colB} />
        </div>
      )}

      <p style={{ margin: 0, fontSize: "13px", opacity: 0.5 }}>
        Approval isn&apos;t available from this page — to approve one side&apos;s claims, run that
        specific situation through{" "}
        <a href="/app/handoff/new" style={{ color: "inherit" }}>
          Start a Handoff
        </a>{" "}
        instead, so it&apos;s unambiguous which result was actually approved.
      </p>
    </div>
  );
}

const selectStyle: React.CSSProperties = {
  padding: "10px 12px",
  borderRadius: "8px",
  border: "1px solid rgba(255,255,255,0.25)",
  background: "rgba(255,255,255,0.05)",
  color: "#fff",
};
