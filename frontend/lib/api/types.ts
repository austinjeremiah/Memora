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

  /**
   * Wallet mode (optional). Supply all five and the server verifies this
   * signature instead of signing itself. The timestamps and nonce must be
   * exactly what /attestation-payload returned — the signature covers them.
   */
  signature?: string;
  signer?: string;
  issued_at?: number;
  expires_at?: number;
  nonce?: number;
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

// ---------------------------------------------------------------------------
// Patients — discovery and the raw stored record
// ---------------------------------------------------------------------------

/**
 * Real patient ids are Synthea UUIDs generated per ingestion run. They cannot
 * be hardcoded anywhere; `GET /patients` is the only way to learn them.
 */
export interface PatientSummaryOut {
  patient_id: string;
  fact_count: number;
  event_count: number;
  memory_version: number;
  kinds: Record<string, number>;
  has_drug_allergy: boolean;
  last_updated: string | null;
}

export interface StoredFactOut {
  name: string;
  status: string | null;
  body: Record<string, unknown> | unknown[] | null;
  created_at: string;
  updated_at: string;
}

/** A lab folded into a trajectory: the series is what a single value cannot say. */
export interface TrendOut {
  name: string;
  test: string | null;
  loinc: string | null;
  unit: string | null;
  direction: string | null;      // rising | falling | stable | single_reading
  delta: number | null;
  readings: number | null;
  latest_value: number | string | null;
  latest_at: string | null;
  series: { value: number; at: string }[];
}

export interface StoredEventOut {
  timestamp: string;
  event_type: string;
  summary: string;
  severity: string | null;
  related_kind: string | null;
  related_name: string | null;
  source_id: string | null;
}

/**
 * The raw record — every WARM fact by kind, every trajectory, the COLD journal.
 * Distinct from ContextOut, which is one situation's ranked and capped plan.
 */
export interface PatientMemoryOut {
  patient_id: string;
  memory_version: number;
  fact_count: number;
  event_count: number;
  facts: Record<string, StoredFactOut[]>;
  trends: TrendOut[];
  events: StoredEventOut[];
  active_situation: Record<string, unknown> | null;
  memory: MemoryStatusOut;
}

// ---------------------------------------------------------------------------
// Situational retrieval
// ---------------------------------------------------------------------------

export interface FactOut {
  kind: string;
  name: string;
  status: string | null;
  body: Record<string, unknown> | unknown[] | null;
  updated_at: string;
}

export interface EventOut {
  event_type: string;
  summary: string;
  timestamp: string;
  severity: string | null;
  related_kind: string | null;
  related_name: string | null;
}

export interface ContextOut {
  patient_id: string;
  situation: string;
  task: string;
  clinician: ClinicianOut;
  facts: FactOut[];
  history: EventOut[];
  memory: MemoryStatusOut;
}

// ---------------------------------------------------------------------------
// Asking a question of memory
// ---------------------------------------------------------------------------

export interface AskRequest {
  question: string;
  clinician_id: string;
}

export interface MatchedRecordOut {
  kind: string;
  name: string;
  status: string | null;
  body: Record<string, unknown> | unknown[] | null;
}

/**
 * `answer` is what a clinician reads first, but it is not trusted on its own:
 * `claims` are the assertions it rests on, each carrying the gate's verdict.
 * When `answered` is false the answer is empty — either nothing matched, or
 * every supporting claim was refused.
 */
export interface AskOut {
  patient_id: string;
  question: string;
  search_terms: string[];
  matched: MatchedRecordOut[];
  answer: string;
  claims: ClaimOut[];
  summary: Record<string, number>;
  answered: boolean;
  model: string;
  memory: MemoryStatusOut;
}

/**
 * Documenting a clinical event. An ordinary write path — this is how an
 * adverse reaction reaches a record — and the thing that makes memory
 * contradict itself, which is what Sentinel then detects.
 */
export interface RecordEventRequest {
  event_type: string;
  summary: string;
  related_kind: string;
  related_name: string;
  severity?: string | null;
  timestamp?: string | null;
  source_id?: string | null;
}

/**
 * What Sentinel did on its own after new information arrived. Nobody asked
 * for this check — new information entering memory is the trigger, which is
 * what makes it the agent acting rather than a feature being invoked.
 */
export interface AutonomousCheckOut {
  ran: boolean;
  situation: string;
  records_checked: number;
  findings: FindingOut[];
  actions_taken: {
    action: string;
    patient_id: string;
    kind: string;
    name: string;
    event_id: string;
    runs_seen: number;
  }[];
}

export interface RecordEventOut {
  patient_id: string;
  event_id: string;
  memory_version: number;
  recorded_at: string;
  autonomous_check: AutonomousCheckOut | null;
}

// ---------------------------------------------------------------------------
// Sentinel — the proactive path. No model is involved in producing any of this.
// ---------------------------------------------------------------------------

export type FindingStatus = "NEW" | "PERSISTING" | "RESOLVED" | "ESCALATED";

export interface FindingOut {
  patient_id: string;
  kind: string;
  name: string;
  status: FindingStatus;
  gate_result: GateResult;
  reason: string;
  detector: string;              // "drift" | "delta"
  first_seen_at: string;
  last_seen_at: string;
  runs_seen: number;
  triggered_rules: string[];
  evidence_event: string | null;
}

export interface SentinelRunRequest {
  situation: Situation;
  patient_ids?: string[] | null; // null = every ingested patient
  escalation_threshold?: number;
}

export interface SentinelRunOut {
  situation: string;
  run_at: string;
  patients_scanned: number;
  records_checked: number;
  summary: Record<string, number>;
  findings: FindingOut[];
  /** Only NEW / ESCALATED / RESOLVED. PERSISTING is tracked but never re-alerts. */
  announceable: FindingOut[];
  digest_commitment: string | null;
}

export interface SinceLastReviewOut {
  patient_id: string;
  situation: string;
  new: FindingOut[];
  persisting: FindingOut[];
  escalated: FindingOut[];
}

// ---------------------------------------------------------------------------
// EIP-712 attestation
// ---------------------------------------------------------------------------

/**
 * Step 1 of the wallet flow. The SERVER derives the state hash, because doing
 * so requires re-verifying every claim against live memory — a browser cannot
 * be trusted to decide what was approved. The wallet only signs what memory
 * has already justified.
 */
export interface AttestationPayloadOut {
  domain: Record<string, unknown>;
  types: Record<string, { name: string; type: string }[]>;
  primary_type: string;
  message: Record<string, string | number>;
  state_hash: string;
  evidence_root: string;
  context_hash: string;
  memory_version: number;
  issued_at: number;
  expires_at: number;
  nonce: number;
  expected_signer: string | null;
  /** "wallet" when a registered address exists, else "synthetic_demo_key". */
  signer_mode: "wallet" | "synthetic_demo_key";
  claim_count: number;
}

export interface AttestationOut {
  clinician_id: string;
  signer: string;
  /** Says in the response itself whether a real wallet or a demo key signed. */
  signer_kind: "registered_wallet" | "synthetic_demo_key";
  signature: string;
  digest: string;
  state_hash: string;
  evidence_root: string;
  context_hash: string;
  memory_version: number;
  issued_at: number;
  expires_at: number;
  nonce: number;
  tx_hash: string;
  block_number: number;
  gas_used: number;
  /** Pays gas; is NOT the signer. That separation is the point. */
  relayer: string;
  basescan_url: string;
}

export interface AttestationVerifyOut {
  state_hash: string;
  exists: boolean;
  signer: string;
  clinician_id: string | null;
  timestamp: number;
  memory_version: number;
  basescan_url: string;
}

export interface CommitmentVerifyOut {
  commitment_hash: string;
  exists: boolean;
  timestamp: number;
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
