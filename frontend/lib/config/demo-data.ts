/**
 * Static config the backend cannot give the frontend at runtime — except
 * where it now can. Reconciled against the real backend source
 * (2026-09-03), not the FRONTEND.md planning doc alone, which had already
 * drifted from it:
 *
 *  - SITUATIONS below is the real `Situation` enum
 *    (backend/memora/context/situations.py).
 *  - CLINICIANS is NOT hardcoded here, unlike the doc's §3.1 suggests.
 *    `GET /clinicians` exists for real (routes.py:116) and returns all
 *    three personas live, including `dr_priya` / SURGEON — the "no surgeon
 *    persona" gap the doc's §0.3 describes no longer exists. Fetch clinicians
 *    with `getClinicians()` from lib/api/client.ts instead of trusting a
 *    static list here, so this file can't silently drift from the backend
 *    the way a hardcoded clinician list would.
 *  - PATIENTS has NO confirmed real IDs. The backend's own demo-ingest path
 *    (`scripts/ingest_demo.py`) pulls patient IDs from Synthea FHIR bundles
 *    at ingest time — they're UUIDs, generated per run, not fixed literals.
 *    "P-10482" appears throughout the backend's own scripts/tests as a
 *    conventional fixture ID, but nothing guarantees it exists in whatever
 *    Sibyl store the API is actually pointed at right now. The placeholder
 *    below is exactly that — a placeholder — flagged loudly rather than
 *    presented as verified. Confirm real IDs against the running store
 *    (e.g. `POST /sentinel/run` with no `patient_ids` returns every known
 *    ingested ID as a side effect) before relying on this list.
 */

// Last reconciled against backend source: 2026-09-03.
export const DEMO_DATA_LAST_SYNCED = "2026-09-03";

export const PATIENTS_ARE_UNCONFIRMED = true;

export const PATIENTS: { id: string; label: string }[] = [
  {
    id: "P-10482",
    label: "P-10482 (conventional fixture ID used throughout backend scripts — UNCONFIRMED, verify it exists in your running store)",
  },
];

export const CLINICIANS_NOTE =
  "Clinicians: fetched live from GET /clinicians, not hardcoded (see lib/api/client.ts's getClinicians()).";

export const SITUATIONS: {
  value: "icu_to_ward" | "pre_operative" | "discharge";
  label: string;
  focusHint: string;
}[] = [
  {
    value: "icu_to_ward",
    label: "ICU → Ward Handoff",
    focusHint: "Medications, allergies, labs, diagnoses",
  },
  {
    value: "pre_operative",
    label: "Pre-Operative Review",
    focusHint: "Allergies, procedures, medications",
  },
  {
    value: "discharge",
    label: "Discharge Planning",
    focusHint: "Diagnoses, medications, procedures",
  },
];
