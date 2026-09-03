"use client";

import { getApiBaseUrl } from "./baseUrl";
import {
  ApproveRequest,
  ClinicianOut,
  CommitmentOut,
  HandoffOut,
  HandoffRequest,
  HealthOut,
  KnownErrorCode,
  MemoraApiError,
  ReadyzOut,
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

// --- Stub points for backend capability that doesn't exist yet (§0.2, §10.4
// of the build doc). Each throws loudly rather than silently faking data, so
// wiring the real endpoint in later is a one-function change here, not a
// hunt through the codebase.

export function listPatients(): Promise<never> {
  throw new Error(
    "listPatients() is not implemented — the backend has no GET /patients endpoint."
  );
}

export function getPatientHistory(_patientId: string): Promise<never> {
  throw new Error(
    "getPatientHistory() is not implemented — the backend has no patient-history endpoint. " +
      "GET /patients/{id}/context exists but returns one situation's retrieval plan, not a raw timeline."
  );
}

export function verifyCommitment(_hash: string): Promise<never> {
  throw new Error(
    "verifyCommitment() is not implemented in this client yet — the backend DOES have " +
      "GET /commitment/{commitment_hash}/verify (confirmed in routes.py), it's just not wired here."
  );
}
