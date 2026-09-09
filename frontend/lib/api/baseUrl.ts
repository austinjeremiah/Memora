"use client";

/**
 * The backend has no documented default host/port anywhere in its repo (no
 * uvicorn.run() call, no Procfile, no README run command) — confirmed by
 * searching the whole backend tree. `http://localhost:8000` below is a
 * plain FastAPI/uvicorn convention, not a verified fact. Settings page
 * lets this be corrected without a rebuild.
 */
/**
 * Resolution order, highest first:
 *
 *   1. what the user typed on the Settings page  (localStorage, this browser)
 *   2. NEXT_PUBLIC_API_BASE_URL                  (baked in at build time)
 *   3. http://localhost:8000                     (local development)
 *
 * The env var matters for any hosted deployment. A page served over HTTPS
 * cannot call an http:// backend -- browsers block it as mixed content -- and
 * "localhost" on a hosted page means the VISITOR's machine, not the server's.
 * So a deployed build needs this set to a public HTTPS backend, or every
 * clinical route will fail to connect.
 */
export const DEFAULT_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "http://localhost:8000";

const STORAGE_KEY = "memora-api-base-url";

export function getApiBaseUrl(): string {
  if (typeof window === "undefined") return DEFAULT_API_BASE_URL;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored && stored.trim() ? stored.trim() : DEFAULT_API_BASE_URL;
  } catch {
    return DEFAULT_API_BASE_URL;
  }
}

export function setApiBaseUrl(url: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, url.trim());
  } catch {
    // localStorage unavailable — base URL just won't persist across reloads
  }
}
