"use client";

import { getApiBaseUrl } from "./baseUrl";
import {
  ApproveRequest,
  AskOut,
  AskRequest,
  AttestationOut,
  AttestationPayloadOut,
  AttestationVerifyOut,
  ClinicianOut,
  CommitmentOut,
  CommitmentVerifyOut,
  ContextOut,
  HandoffOut,
  HandoffRequest,
  HealthOut,
  KnownErrorCode,
  MemoraApiError,
  PatientMemoryOut,
  PatientSummaryOut,
  RecordEventOut,
  RecordEventRequest,
  ReadyzOut,
  SentinelRunOut,
  SentinelRunRequest,
  Situation,
  SinceLastReviewOut,
  OpenSessionOut,
  PriorContextOut,
  RuntimeOut,
  SessionOut,
  ThreadOut,
} from "./types";

/**
 * One function per real backend endpoint, typed request/response matching
 * `types.ts` exactly. This is the ONLY file that should ever need a base-URL
 * check — nothing else in the app should call `fetch` directly against the
 * backend.
 */

/**
 * Two genuinely different response shapes exist, confirmed by actually
 * running the backend and inspecting real bytes on the wire (not assumed
 * from reading the Python):
 *
 *  1. main.py's @app.exception_handler-registered errors (SibylUnavailableError,
 *     SibylPatientUnknownError, SibylQuotaExceededError, LLMUnavailableError,
 *     BaseUnavailableError, CommitmentExistsError) build their own JSONResponse
 *     directly — the body is FLAT: { error: "...", detail: "..." }.
 *
 *  2. Every inline `raise HTTPException(..., detail=X)` in routes.py
 *     (readyz's 503, the 400 unknown-clinician, 422 unknown-situation, 400
 *     patient_id mismatch, 403 not-authorised, 409 claim_not_verifiable) goes
 *     through FastAPI's default HTTPException handler, which wraps whatever
 *     `detail` value was passed inside its OWN top-level { "detail": X } —
 *     so X ends up NESTED one level deeper, and X can itself be a string or
 *     an object depending on the route. Confirmed live: readyz's actual body
 *     is `{"detail": {"status": "not_ready", "sibyl": false, "error": "..."}}`,
 *     not the flat shape a first read of routes.py's `detail={...}` call
 *     site would suggest.
 */
function unwrapDetail(obj: Record<string, unknown>): unknown {
  return "detail" in obj ? obj.detail : obj;
}

async function parseErrorBody(res: Response): Promise<{ code: KnownErrorCode; detail: string }> {
  let raw: unknown = null;
  try {
    raw = await res.json();
  } catch {
    // non-JSON body — fall through to status-based mapping below
  }

  if (raw && typeof raw === "object") {
    const top = raw as Record<string, unknown>;
    const inner = unwrapDetail(top);

    // Nested object shapes from routes.py's inline HTTPExceptions, once
    // unwrapped from FastAPI's { detail: ... } envelope.
    if (inner && typeof inner === "object") {
      const obj = inner as Record<string, unknown>;

      // readyz's 503: { status, sibyl, error }
      if (typeof obj.sibyl === "boolean" && typeof obj.error === "string") {
        return { code: "sibyl_unavailable", detail: obj.error };
      }
      // approve/attest's 409: { error: "claim_not_verifiable", detail, claim, reason }
      if (obj.error === "claim_not_verifiable") {
        const reason = typeof obj.reason === "string" ? ` (${obj.reason})` : "";
        const claim = typeof obj.claim === "string" ? `"${obj.claim}"` : "a submitted claim";
        return {
          code: "claim_not_verifiable",
          detail: `${String(obj.detail ?? "Refusing to commit.")} ${claim}${reason}`,
        };
      }
      // main.py's flat { error, detail } custom handlers
      if (typeof obj.error === "string") {
        const known: KnownErrorCode[] = [
          "sibyl_unavailable",
          "patient_unknown",
          "memory_quota_exceeded",
          "llm_unavailable",
          "base_unavailable",
          "commitment_exists",
        ];
        const code = known.includes(obj.error as KnownErrorCode)
          ? (obj.error as KnownErrorCode)
          : "unexpected";
        return { code, detail: typeof obj.detail === "string" ? obj.detail : res.statusText };
      }
    }

    // Plain-string detail — the remaining inline HTTPExceptions in routes.py.
    if (typeof inner === "string") {
      if (res.status === 400 && inner.startsWith("Unknown clinician_id"))
        return { code: "unknown_clinician", detail: inner };
      if (res.status === 422 && inner.startsWith("Unknown situation"))
        return { code: "unknown_situation", detail: inner };
      if (res.status === 400 && inner.includes("must match"))
        return { code: "patient_id_mismatch", detail: inner };
      if (res.status === 403) return { code: "not_authorised", detail: inner };
      return { code: "unexpected", detail: inner };
    }
  }

  return { code: "unexpected", detail: `${res.status} ${res.statusText}` };
}

async function request<TResponse>(
  path: string,
  init?: RequestInit
): Promise<TResponse> {
  const url = `${getApiBaseUrl()}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new MemoraApiError({
      status: null,
      code: "network_error",
      detail: `Could not reach the backend at ${url}. Check your connection and try again.`,
    });
  }

  if (!res.ok) {
    const { code, detail } = await parseErrorBody(res);
    throw new MemoraApiError({ status: res.status, code, detail });
  }

  return (await res.json()) as TResponse;
}

export function getHealth(): Promise<HealthOut> {
  return request<HealthOut>("/health");
}

export function getReadyz(): Promise<ReadyzOut> {
  return request<ReadyzOut>("/readyz");
}

export function getClinicians(): Promise<ClinicianOut[]> {
  return request<ClinicianOut[]>("/clinicians");
}

export function requestHandoff(body: HandoffRequest): Promise<HandoffOut> {
  return request<HandoffOut>("/handoff", { method: "POST", body: JSON.stringify(body) });
}

export function approveHandoff(
  patientId: string,
  body: ApproveRequest
): Promise<CommitmentOut> {
  return request<CommitmentOut>(`/handoff/${encodeURIComponent(patientId)}/approve`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Patients
// ---------------------------------------------------------------------------

/**
 * Every patient in the store. This is the ONLY way to learn patient ids — they
 * are Synthea UUIDs generated per ingestion run, so nothing may hardcode them.
 * (The three stubs that used to throw here are all implemented now; the
 * backend gained GET /patients and GET /patients/{id}/memory for exactly this.)
 */
export function listPatients(): Promise<PatientSummaryOut[]> {
  return request<PatientSummaryOut[]>("/patients");
}

/** The raw stored record — unfiltered by situation. */
export function getPatientMemory(
  patientId: string,
  eventLimit = 200
): Promise<PatientMemoryOut> {
  return request<PatientMemoryOut>(
    `/patients/${encodeURIComponent(patientId)}/memory?event_limit=${eventLimit}`
  );
}

/** One situation's ranked, capped retrieval plan. No model involved. */
export function getPatientContext(
  patientId: string,
  situation: Situation,
  clinicianId: string
): Promise<ContextOut> {
  const q = new URLSearchParams({ situation, clinician_id: clinicianId });
  return request<ContextOut>(
    `/patients/${encodeURIComponent(patientId)}/context?${q}`
  );
}

/**
 * Ask a question of a patient's memory.
 *
 * Retrieval is driven by the question via Sibyl's FTS5 index rather than by a
 * fixed situation. Everything after retrieval is unchanged -- the same gate
 * decides, so a question earns the model no extra latitude.
 */
export function askMemory(patientId: string, body: AskRequest): Promise<AskOut> {
  return request<AskOut>(`/patients/${encodeURIComponent(patientId)}/ask`, {
    method: "POST", body: JSON.stringify(body),
  });
}

/** Document a clinical event against a patient's journal. */
export function recordEvent(
  patientId: string,
  body: RecordEventRequest
): Promise<RecordEventOut> {
  return request<RecordEventOut>(
    `/patients/${encodeURIComponent(patientId)}/events`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

// ---------------------------------------------------------------------------
// Sentinel
// ---------------------------------------------------------------------------

export function runSentinel(body: SentinelRunRequest): Promise<SentinelRunOut> {
  return request<SentinelRunOut>("/sentinel/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function sinceLastReview(
  patientId: string,
  situation: Situation
): Promise<SinceLastReviewOut> {
  const q = new URLSearchParams({ patient_id: patientId, situation });
  return request<SinceLastReviewOut>(`/sentinel/since-last-review?${q}`);
}

// ---------------------------------------------------------------------------
// Attestation
// ---------------------------------------------------------------------------

/** Step 1: what the wallet should sign. The server derives it from live memory. */
export function getAttestationPayload(
  patientId: string,
  body: ApproveRequest
): Promise<AttestationPayloadOut> {
  return request<AttestationPayloadOut>(
    `/handoff/${encodeURIComponent(patientId)}/attestation-payload`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

/**
 * Step 2: record it. Include signature/signer/issued_at/expires_at/nonce for
 * wallet mode; omit them and the server signs with the synthetic demo key.
 */
export function attestHandoff(
  patientId: string,
  body: ApproveRequest
): Promise<AttestationOut> {
  return request<AttestationOut>(
    `/handoff/${encodeURIComponent(patientId)}/attest`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

export function verifyAttestation(stateHash: string): Promise<AttestationVerifyOut> {
  return request<AttestationVerifyOut>(
    `/attestation/${encodeURIComponent(stateHash)}/verify`
  );
}

export function verifyCommitment(hash: string): Promise<CommitmentVerifyOut> {
  return request<CommitmentVerifyOut>(
    `/commitment/${encodeURIComponent(hash)}/verify`
  );
}

// ---------------------------------------------------------------------------
// Sessions and threads
// ---------------------------------------------------------------------------

/** Identity of the API process. Changes only when the backend restarts. */
export function getRuntime(): Promise<RuntimeOut> {
  return request<RuntimeOut>("/runtime");
}

/**
 * Open a clinician session and receive what it inherited.
 *
 * The response's `prior` is read BEFORE the new session is written, so a
 * session never inherits itself, and `crossed_restart` reports whether any of
 * what it inherited was written by a process that is no longer running.
 */
export function openSession(patientId: string, clinicianId: string): Promise<OpenSessionOut> {
  return request<OpenSessionOut>(`/patients/${encodeURIComponent(patientId)}/sessions`, {
    method: "POST", body: JSON.stringify({ clinician_id: clinicianId }),
  });
}

export function listSessions(patientId: string): Promise<SessionOut[]> {
  return request<SessionOut[]>(`/patients/${encodeURIComponent(patientId)}/sessions`);
}

export function closeSession(patientId: string, sessionId: string): Promise<SessionOut> {
  return request<SessionOut>(
    `/patients/${encodeURIComponent(patientId)}/sessions/${encodeURIComponent(sessionId)}/close`,
    { method: "POST" }
  );
}

export function getPriorContext(patientId: string, excludeSessionId?: string
                                ): Promise<PriorContextOut> {
  const q = excludeSessionId
    ? `?exclude_session_id=${encodeURIComponent(excludeSessionId)}` : "";
  return request<PriorContextOut>(
    `/patients/${encodeURIComponent(patientId)}/prior-context${q}`);
}

export function openThread(patientId: string, sessionId: string, title?: string
                           ): Promise<ThreadOut> {
  return request<ThreadOut>(`/patients/${encodeURIComponent(patientId)}/threads`, {
    method: "POST", body: JSON.stringify({ session_id: sessionId, title: title ?? null }),
  });
}

export function listThreads(patientId: string, sessionId?: string): Promise<ThreadOut[]> {
  const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  return request<ThreadOut[]>(`/patients/${encodeURIComponent(patientId)}/threads${q}`);
}
