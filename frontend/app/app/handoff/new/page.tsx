"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getClinicians } from "@/lib/api/client";
import { ClinicianOut, Situation } from "@/lib/api/types";
import { PATIENTS, PATIENTS_ARE_UNCONFIRMED, SITUATIONS } from "@/lib/config/demo-data";
import SibylWarningBanner from "@/app/app/_components/SibylWarningBanner";

export default function StartHandoffPage() {
  const router = useRouter();

  const [patientId, setPatientId] = useState("");
  const [situation, setSituation] = useState<Situation | "">("");
  const [clinicianId, setClinicianId] = useState("");

  const [clinicians, setClinicians] = useState<ClinicianOut[] | null>(null);
  const [clinicianError, setClinicianError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getClinicians()
      .then((list) => {
        if (!cancelled) setClinicians(list);
      })
      .catch((e) => {
        if (!cancelled)
          setClinicianError(e instanceof Error ? e.message : "Could not load clinicians.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const canSubmit = Boolean(patientId && situation && clinicianId);

  const selectedClinician = clinicians?.find((c) => c.id === clinicianId) ?? null;

  const submit = () => {
    if (!canSubmit) return;
    const params = new URLSearchParams({
      patientId,
      situation,
      clinicianId,
    });
    router.push(`/app/handoff/result?${params.toString()}`);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <h1 style={{ margin: 0 }}>Start a Handoff</h1>

      <SibylWarningBanner />

      {!(patientId && situation && clinicianId) && (
        <p style={{ margin: 0, opacity: 0.7 }}>
          Choose a patient, situation, and clinician to begin.
        </p>
      )}

      <section style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <label htmlFor="patient" style={{ fontSize: "13px", opacity: 0.7 }}>
          Patient
        </label>
        <select
          id="patient"
          value={patientId}
          onChange={(e) => setPatientId(e.target.value)}
          style={selectStyle}
        >
          <option value="">Select a patient...</option>
          {PATIENTS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
        {PATIENTS_ARE_UNCONFIRMED && (
          <p style={{ margin: 0, fontSize: "12px", color: "#ffb020" }}>
            This patient ID is an unconfirmed placeholder — the backend has no way to
            list real ingested patient IDs. Verify it exists in your running Sibyl
            store before relying on it. See lib/config/demo-data.ts.
          </p>
        )}
      </section>

      <section style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <label htmlFor="situation" style={{ fontSize: "13px", opacity: 0.7 }}>
          Situation
        </label>
        <select
          id="situation"
          value={situation}
          onChange={(e) => setSituation(e.target.value as Situation)}
          style={selectStyle}
        >
          <option value="">Select a situation...</option>
          {SITUATIONS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        {situation && (
          <p style={{ margin: 0, fontSize: "12px", opacity: 0.6 }}>
            Focus: {SITUATIONS.find((s) => s.value === situation)?.focusHint} — descriptive
            copy only, mirrors the backend's own SITUATION_FOCUS for context; has no effect
            on the actual request.
          </p>
        )}
      </section>

      <section style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <label htmlFor="clinician" style={{ fontSize: "13px", opacity: 0.7 }}>
          Clinician
        </label>
        {clinicianError && (
          <p style={{ margin: 0, fontSize: "13px", color: "#ff6b6b" }}>
            Could not load clinicians from the backend: {clinicianError}
          </p>
        )}
        {!clinicianError && clinicians === null && (
          <p style={{ margin: 0, fontSize: "13px", opacity: 0.6 }}>Loading clinicians...</p>
        )}
        {clinicians !== null && (
          <select
            id="clinician"
            value={clinicianId}
            onChange={(e) => setClinicianId(e.target.value)}
            style={selectStyle}
          >
            <option value="">Select a clinician...</option>
            {clinicians.map((c) => (
              <option key={c.id} value={c.id} disabled={!c.can_approve_handoff}>
                {c.name} — {c.role}
                {!c.can_approve_handoff ? " (cannot approve handoffs)" : ""}
              </option>
            ))}
          </select>
        )}
        {selectedClinician && !selectedClinician.can_approve_handoff && (
          <p style={{ margin: 0, fontSize: "12px", color: "#ffb020" }}>
            {selectedClinician.name} cannot approve a handoff (role: {selectedClinician.role}) —
            you can still get a Handoff Brief, but the Approve &amp; Commit step will 403
            if attempted with this clinician.
          </p>
        )}
      </section>

      <button
        type="button"
        onClick={submit}
        disabled={!canSubmit}
        style={{
          alignSelf: "flex-start",
          padding: "12px 22px",
          borderRadius: "10px",
          border: "none",
          background: canSubmit ? "#fff" : "rgba(255,255,255,0.1)",
          color: canSubmit ? "#000" : "rgba(255,255,255,0.4)",
          fontWeight: 600,
          cursor: canSubmit ? "pointer" : "default",
        }}
      >
        Get Handoff Brief
      </button>
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
