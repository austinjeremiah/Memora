"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { getHealth, getReadyz } from "./client";

interface AppStatus {
  backendReachable: boolean | null; // null = not checked yet
  sibylReady: boolean | null;
  lastCheckedAt: number | null;
  lastKnownDbSizeBytes: number | null;
  lastKnownDbSizeCheckedAt: number | null;
  checking: boolean;
  refresh: () => Promise<void>;
  reportDbSize: (bytes: number) => void;
}

const AppStatusCtx = createContext<AppStatus | null>(null);

const POLL_MS = 45_000;

export function AppStatusProvider({ children }: { children: React.ReactNode }) {
  const [backendReachable, setBackendReachable] = useState<boolean | null>(null);
  const [sibylReady, setSibylReady] = useState<boolean | null>(null);
  const [lastCheckedAt, setLastCheckedAt] = useState<number | null>(null);
  const [checking, setChecking] = useState(false);
  const [lastKnownDbSizeBytes, setLastKnownDbSizeBytes] = useState<number | null>(null);
  const [lastKnownDbSizeCheckedAt, setLastKnownDbSizeCheckedAt] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    setChecking(true);
    try {
      await getHealth();
      setBackendReachable(true);
    } catch {
      setBackendReachable(false);
      setSibylReady(null);
      setLastCheckedAt(Date.now());
      setChecking(false);
      return;
    }

    try {
      await getReadyz();
      setSibylReady(true);
    } catch {
      // readyz returns 503 with sibyl:false when Sibyl itself is unreachable
      // — the backend answered, so it's a distinct condition from
      // backendReachable=false, not the same failure.
      setSibylReady(false);
    }

    setLastCheckedAt(Date.now());
    setChecking(false);
  }, []);

  const reportDbSize = useCallback((bytes: number) => {
    setLastKnownDbSizeBytes(bytes);
    setLastKnownDbSizeCheckedAt(Date.now());
  }, []);

  const didInit = useRef(false);
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;
    void refresh();
    const id = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <AppStatusCtx.Provider
      value={{
        backendReachable,
        sibylReady,
        lastCheckedAt,
        lastKnownDbSizeBytes,
        lastKnownDbSizeCheckedAt,
        checking,
        refresh,
        reportDbSize,
      }}
    >
      {children}
    </AppStatusCtx.Provider>
  );
}

export function useAppStatus(): AppStatus {
  const ctx = useContext(AppStatusCtx);
  if (!ctx) throw new Error("useAppStatus() must be used inside <AppStatusProvider>");
  return ctx;
}
