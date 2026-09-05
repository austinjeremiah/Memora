/**
 * Static config the backend genuinely cannot supply at runtime.
 *
 * There is deliberately NO patient list here. Real patient ids are Synthea
 * UUIDs generated per ingestion run — they differ between stores and cannot be
 * known ahead of time. An earlier version shipped a hardcoded `P-10482`, which
 * was a fixture id from the backend's own scripts and would 404 against any
 * real store. Use `listPatients()` from lib/api/client.ts.
 *
 * Clinicians are likewise fetched live from `GET /clinicians` rather than
 * duplicated here, so this file cannot drift from the backend.
 */

export const SITUATIONS: {
  value: "icu_to_ward" | "pre_operative" | "discharge";
  label: string;
  focusHint: string;
}[] = [
  {
    value: "icu_to_ward",
    label: "ICU → Ward handoff",
    focusHint: "Medications, allergies, lab trends, diagnoses",
  },
  {
    value: "pre_operative",
    label: "Pre-operative review",
    focusHint: "Allergies, procedures, medications",
  },
  {
    value: "discharge",
    label: "Discharge planning",
    focusHint: "Diagnoses, medications, procedures",
  },
];

/** Human labels for the ontology's entity kinds. */
export const KIND_LABELS: Record<string, string> = {
  medication: "Medications",
  allergy: "Allergies",
  diagnosis: "Diagnoses",
  procedure: "Procedures",
  lab_trend: "Lab trends",
  care_phase: "Encounters",
};
