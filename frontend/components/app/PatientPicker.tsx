"use client";

import { useEffect, useState } from "react";
import { listPatients } from "@/lib/api/client";
import { MemoraApiError, PatientSummaryOut } from "@/lib/api/types";
import { Field, Notice } from "./ui";

/**
 * Patient selection, always from the live store.
 *
 * Shared so no page can reintroduce a hardcoded id. Real ids are Synthea
 * UUIDs generated per ingestion run — an earlier hardcoded fixture id would
 * have 404'd against any real store.
 */
export default function PatientPicker({ value, onChange, label = "Patient" }: {
  value: string;
  onChange: (patientId: string) => void;
  label?: string;
}) {
  const [patients, setPatients] = useState<PatientSummaryOut[] | null>(null);
  const [error, setError] = useState<MemoraApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    listPatients()
      .then((list) => {
        if (cancelled) return;
        setPatients(list);
        // Preselect when there is exactly one obvious choice.
        if (!value && list.length === 1) onChange(list[0].patient_id);
      })
      .catch((e) => !cancelled && setError(e as MemoraApiError));
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <Notice tone="error" title="Could not load patients">
        {error.detail}
      </Notice>
    );
  }

  return (
    <Field
      label={label}
      hint={patients
        ? `${patients.length} in the store · ids come from Synthea, not from this app`
        : "Reading from memory…"}
    >
      <select
        className="select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={!patients}
      >
        <option value="">
          {patients ? "Select a patient…" : "Loading…"}
        </option>
        {patients?.map((p) => (
          <option key={p.patient_id} value={p.patient_id}>
            {p.patient_id.slice(0, 8)}… — {p.fact_count} facts, {p.event_count} events
            {p.has_drug_allergy ? " · drug allergy" : ""}
          </option>
        ))}
      </select>
    </Field>
  );
}
