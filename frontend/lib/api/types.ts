/**
 * Types mirror `backend/memora/api/schemas.py` field-for-field, confirmed
 * against the real source (not the FRONTEND.md planning doc, which had
 * already drifted from it in several places — e.g. no flat
 * `sibyl_db_size_bytes`, `clinician` is an object not a string, `approve`
 * returns `CommitmentOut` with many more fields than the doc assumed).
 * If the backend schema changes, update here first — everything else in
 * lib/api/ depends on these.
 */

export type Situation = "icu_to_ward" | "pre_operative" | "discharge";

export type ClinicianRole =
  | "icu_physician"
  | "ward_physician"
  | "surgeon"
  | "system";

export type GateResult = "ALLOW" | "BLOCK" | "NEEDS_REVIEW";

export interface ClinicianOut {
  id: string;
  name: string;
  role: ClinicianRole;
  can_approve_handoff: boolean;
}

export interface SourceEventOut {
  source_id: string | null;
  event_type: string;
  timestamp: string;
  summary: string;
  severity: string | null;
}

export interface ClaimOut {
  text: string;
  gate_result: GateResult;
  reason: string;
  triggered_rules: string[];
  source_kind: string | null;
  source_name: string | null;
  fact_status: string | null;
  source_events: SourceEventOut[];
}

export interface MemoryStatusOut {
  db_size_bytes: number;
  soft_cap_bytes: number | null;
  pct_used: number | null;
}

export interface HandoffRequest {
  patient_id: string;
  situation: Situation;
  clinician_id: string;
}

export interface HandoffOut {
  patient_id: string;
  situation: string;
  task: string;
  clinician: ClinicianOut;
  claims: ClaimOut[];
  summary: Record<string, number>;
  proposed_count: number;
  model: string;
  memory: MemoryStatusOut;
}

export interface ApproveClaimIn {
  text: string;
  related_kind?: string | null;
  related_name?: string | null;
}

export interface ApproveRequest {
  patient_id: string;
  situation: Situation;
  clinician_id: string;
  claims: ApproveClaimIn[];
}

export interface CommitmentOut {
  patient_id: string;
  situation: string;
  approved_by: string;
  claim_count: number;
  commitment_hash: string;
  label: string;
  tx_hash: string;
  block_number: number;
  gas_used: number;
  committer: string;
  basescan_url: string;
}

export interface HealthOut {
  status: string;
  service: string;
}

export interface ReadyzOut {
  status: "ready";
  sibyl: true;
  db_path: string;
}

/**
 * The real error contract, from `main.py`'s app-level exception handlers
 * plus the inline HTTPExceptions in `routes.py`. Every mapped error body is
 * `{ error, detail }` except two: readyz's 503 body is
 * `{ status, sibyl, error }`, and approve's 409 "claim_not_verifiable" body
 * carries `{ error, detail, claim, reason }`. `MemoraApiError` normalizes
 * all of these into one shape the UI can switch on.
 */
export type KnownErrorCode =
  | "sibyl_unavailable"
  | "patient_unknown"
  | "memory_quota_exceeded"
  | "llm_unavailable"
  | "base_unavailable"
  | "commitment_exists"
  | "claim_not_verifiable"
  | "unknown_clinician"
  | "unknown_situation"
  | "not_authorised"
  | "patient_id_mismatch"
  | "network_error"
  | "unexpected";

export class MemoraApiError extends Error {
  readonly status: number | null;
  readonly code: KnownErrorCode;
  readonly detail: string;

  constructor(params: { status: number | null; code: KnownErrorCode; detail: string }) {
    super(params.detail);
    this.status = params.status;
    this.code = params.code;
    this.detail = params.detail;
  }
}
