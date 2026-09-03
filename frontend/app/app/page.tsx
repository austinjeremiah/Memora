"use client";

import Link from "next/link";
import { useAppStatus } from "@/lib/api/AppStatusContext";

export default function HomePage() {
  const { backendReachable, sibylReady, checking } = useAppStatus();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      <h1 style={{ margin: 0 }}>MEMORA — System Status</h1>
      <p style={{ opacity: 0.75, margin: 0 }}>
        Persistent clinical memory with a deterministic safety gate. This confirms the
        backend and Sibyl memory are reachable before you start a handoff.
      </p>

      <section
        style={{
          border: "1px solid rgba(255,255,255,0.15)",
          borderRadius: "12px",
          padding: "20px",
          display: "flex",
          flexDirection: "column",
          gap: "10px",
        }}
      >
        {backendReachable === null && (
          // First mount, nothing fetched yet — a skeleton shape, not the
          // "actively re-checking" spinner text used lower down (§9.6).
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }} aria-label="Loading status">
            <div style={{ height: "16px", width: "55%", borderRadius: "4px", background: "rgba(255,255,255,0.08)" }} />
            <div style={{ height: "16px", width: "40%", borderRadius: "4px", background: "rgba(255,255,255,0.08)" }} />
          </div>
        )}

        {/* backendReachable === false is handled by BackendGate one level up —
            it replaces this whole page before it renders, so there's no
            corresponding branch here to duplicate that message. */}

        {backendReachable === true && (
          <p style={{ margin: 0, color: "#4ade80" }}>Backend is reachable.</p>
        )}

        {backendReachable === true && sibylReady === false && (
          <p style={{ margin: 0, color: "#ffb020" }}>
            Backend is up, but Sibyl memory isn&apos;t available right now. Handoff
            requests will fail until this is resolved — you can still browse this app.
          </p>
        )}

        {backendReachable === true && sibylReady === true && (
          <p style={{ margin: 0, color: "#4ade80" }}>Sibyl memory is ready.</p>
        )}
      </section>

      <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
        <Link
          href="/app/handoff/new"
          style={{
            padding: "12px 20px",
            borderRadius: "10px",
            background: "#fff",
            color: "#000",
            textDecoration: "none",
            fontWeight: 600,
          }}
        >
          Start a New Handoff
        </Link>
        <Link
          href="/app/compare"
          style={{
            padding: "12px 20px",
            borderRadius: "10px",
            border: "1px solid rgba(255,255,255,0.3)",
            color: "#fff",
            textDecoration: "none",
          }}
        >
          Compare Situations
        </Link>
      </div>

      {checking && backendReachable !== null && (
        <p style={{ margin: 0, opacity: 0.5, fontSize: "13px" }}>Refreshing status...</p>
      )}
    </div>
  );
}
