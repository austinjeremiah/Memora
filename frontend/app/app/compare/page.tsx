"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getClinicians, requestHandoff } from "@/lib/api/client";
import { useAppStatus } from "@/lib/api/AppStatusContext";
import {
  ClinicianOut, HandoffOut, MemoraApiError, Situation,
} from "@/lib/api/types";
import { SITUATIONS } from "@/lib/config/demo-data";
import PatientPicker from "@/components/app/PatientPicker";
import ClaimCard, { GateSummary } from "@/components/app/ClaimCard";
import {
  Button, Card, EmptyState, Field, Notice, Section, SkeletonList,
} from "@/components/app/ui";

type Column =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; data: HandoffOut }
  | { status: "error"; error: MemoraApiError };

/**
 * MEMORA's central claim, side by side: the SAME patient and the SAME store,
 * asked three different clinical questions, producing three different
 * answers. Not because the data changed -- because what matters changed.
 */
export default function ComparePage() {
  return (
    <Suspense fallback={<SkeletonList rows={3} />}>
      <CompareInner />
    </Suspense>
  );
}

function CompareInner() {
  const params = useSearchParams();
  const { reportMemory } = useAppStatus();

  const [patientId, setPatientId] = useState(params.get("patientId") ?? "");
  const [clinicianId, setClinicianId] = useState("");
  const [clinicians, setClinicians] = useState<ClinicianOut[] | null>(null);
  const [columns, setColumns] = useState<Record<string, Column>>({});

  useEffect(() => {
    let cancelled = false;
    getClinicians().then((list) => {
      if (cancelled) return;
      setClinicians(list);
      if (!clinicianId && list.length) setClinicianId(list[0].id);
    }).catch(() => undefined);
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = () => {
    if (!patientId || !clinicianId) return;
    setColumns(Object.fromEntries(SITUATIONS.map((s) => [s.value, { status: "loading" }])));
    for (const s of SITUATIONS) {
      requestHandoff({ patient_id: patientId, situation: s.value, clinician_id: clinicianId })
        .then((data) => {
          reportMemory(data.memory);
          setColumns((prev) => ({ ...prev, [s.value]: { status: "loaded", data } }));
        })
        .catch((e) => setColumns((prev) => ({
          ...prev, [s.value]: { status: "error", error: e as MemoraApiError },
        })));
    }
  };

  const ran = Object.keys(columns).length > 0;

  return (
    <div className="stack stack--loose">
      <div className="stack stack--tight">
        <h1 className="page-title">Compare situations</h1>
        <p className="subtle" style={{ margin: 0, maxWidth: 660 }}>
          One patient, one memory store, three clinical questions. The subsets
          differ because a retrieval plan is compiled from the situation — the
          same inputs always produce the same plan.
        </p>
      </div>

      <Card>
        <div className="stack">
          <PatientPicker value={patientId} onChange={setPatientId} />
          <Field label="Clinician" hint="Their role also decides what the gate permits">
            <select className="select" value={clinicianId}
                    onChange={(e) => setClinicianId(e.target.value)} disabled={!clinicians}>
              {clinicians?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} — {c.role.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </Field>
          <div>
            <Button variant="primary" onClick={run} disabled={!patientId || !clinicianId}>
              {ran ? "Run again" : "Run all three situations"}
            </Button>
          </div>
        </div>
      </Card>

      {!ran && (
        <EmptyState title="Nothing compared yet">
          Pick a patient and run — the three situations are requested in parallel
          against the same store.
        </EmptyState>
      )}

      {ran && (
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" }}>
          {SITUATIONS.map((s) => {
            const col = columns[s.value] ?? { status: "idle" as const };
            return (
              <Section
                key={s.value}
                title={s.label}
                action={col.status === "loaded" ? <GateSummary claims={col.data.claims} /> : undefined}
              >
                {col.status === "loading" && <SkeletonList rows={3} />}
                {col.status === "error" && (
                  <Notice tone="error" title="Failed">{col.error.detail}</Notice>
                )}
                {col.status === "loaded" && (
                  <div className="stack">
                    <span className="dim">
                      {col.data.task.replace(/_/g, " ")} · recalled{" "}
                      {col.data.proposed_count} proposals
                    </span>
                    {col.data.claims.map((c) => (
                      <ClaimCard key={c.text} claim={c} />
                    ))}
                  </div>
                )}
              </Section>
            );
          })}
        </div>
      )}
    </div>
  );
}
