"use client";

/**
 * The backend has no documented default host/port anywhere in its repo (no
 * uvicorn.run() call, no Procfile, no README run command) — confirmed by
 * searching the whole backend tree. `http://localhost:8000` below is a
 * plain FastAPI/uvicorn convention, not a verified fact. Settings page
 * lets this be corrected without a rebuild.
 */
export const DEFAULT_API_BASE_URL = "http://localhost:8000";

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
