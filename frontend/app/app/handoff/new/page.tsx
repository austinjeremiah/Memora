"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getClinicians } from "@/lib/api/client";
import { ClinicianOut, MemoraApiError, Situation } from "@/lib/api/types";
import { SITUATIONS } from "@/lib/config/demo-data";
import PatientPicker from "@/components/app/PatientPicker";
import { Button, Card, Field, Notice, SkeletonList } from "@/components/app/ui";

export default function StartHandoffPage() {
  return (
    <Suspense fallback={<SkeletonList rows={3} />}>
      <StartHandoffInner />
    </Suspense>
  );
}

function StartHandoffInner() {
  const router = useRouter();
  const params = useSearchParams();

  // Prefilled when arriving from a patient's memory page.
  const [patientId, setPatientId] = useState(params.get("patientId") ?? "");
  const [situation, setSituation] = useState<Situation | "">("");
  const [clinicianId, setClinicianId] = useState("");

  const [clinicians, setClinicians] = useState<ClinicianOut[] | null>(null);
  const [error, setError] = useState<MemoraApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    getClinicians()
      .then((list) => !cancelled && setClinicians(list))
      .catch((e) => !cancelled && setError(e as MemoraApiError));
    return () => { cancelled = true; };
  }, []);

  const clinician = clinicians?.find((c) => c.id === clinicianId) ?? null;
  const focus = SITUATIONS.find((s) => s.value === situation);
  const ready = Boolean(patientId && situation && clinicianId);

  const submit = () => {
    if (!ready) return;
    router.push(`/app/handoff/result?${new URLSearchParams({
      patientId, situation, clinicianId,
    })}`);
  };

  return (
    <div className="stack stack--loose">
      <div className="stack stack--tight">
        <h1 className="page-title">New handoff</h1>
        <p className="subtle" style={{ margin: 0, maxWidth: 620 }}>
          The situation decides what gets recalled; the clinician&apos;s role decides
          what they are allowed to see. Both are part of the gate&apos;s decision, not
          presentation applied afterwards.
        </p>
      </div>

      {error && <Notice tone="error" title="Could not load clinicians">{error.detail}</Notice>}

      <Card>
        <div className="stack">
          <PatientPicker value={patientId} onChange={setPatientId} />
        </div>

        <div className="grid grid--2" style={{ marginTop: "var(--space-4)" }}>
          <Field
            label="Clinical situation"
            hint={focus ? `Recalls: ${focus.focusHint}` : undefined}
          >
            <select className="select" value={situation}
                    onChange={(e) => setSituation(e.target.value as Situation)}>
              <option value="">Select a situation…</option>
              {SITUATIONS.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </Field>

          <Field
            label="Clinician"
            hint={clinician
              ? `${clinician.role.replace(/_/g, " ")}${clinician.can_approve_handoff
                  ? " · can approve a handover"
                  : " · cannot approve a handover"}`
              : "Fetched live from the backend, not hardcoded"}
          >
            <select className="select" value={clinicianId}
                    onChange={(e) => setClinicianId(e.target.value)}
                    disabled={!clinicians}>
              <option value="">{clinicians ? "Select a clinician…" : "Loading…"}</option>
              {clinicians?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} — {c.role.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </Field>
        </div>

        {clinician && !clinician.can_approve_handoff && (
          <div style={{ marginTop: "var(--space-4)" }}>
            <Notice tone="warn">
              {clinician.name} can review this handover but cannot approve it. That
              restriction comes from the same authority table the gate uses.
            </Notice>
          </div>
        )}

        <div className="card__footer row row--between">
          <span className="dim">
            {ready ? "Ready to run." : "Pick a patient, situation, and clinician to continue."}
          </span>
          <Button variant="primary" onClick={submit} disabled={!ready}>
            Run handoff
          </Button>
        </div>
      </Card>
    </div>
  );
}
