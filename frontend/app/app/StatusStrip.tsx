"use client";

import { useAppStatus } from "@/lib/api/AppStatusContext";

function formatBytes(bytes: number): string {
  return `${(bytes / 1024).toFixed(0)} KB`;
}

export default function StatusStrip() {
  const {
    backendReachable,
    sibylReady,
    checking,
    lastCheckedAt,
    lastKnownDbSizeBytes,
    lastKnownDbSizeCheckedAt,
    refresh,
  } = useAppStatus();

  const FREE_TIER_CAP_BYTES = 2_097_152; // documented Sibyl free-tier cap

  let backendLabel = "Checking backend...";
  if (backendReachable === true) backendLabel = "Backend: reachable";
  if (backendReachable === false) backendLabel = "Backend: unreachable";

  let sibylLabel = "";
  if (backendReachable === true) {
    if (sibylReady === true) sibylLabel = "Sibyl: ready";
    else if (sibylReady === false) sibylLabel = "Sibyl: unavailable";
    else sibylLabel = "Sibyl: checking...";
  }

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "16px",
        alignItems: "center",
        padding: "10px 20px",
        borderBottom: "1px solid rgba(255,255,255,0.12)",
        fontSize: "13px",
        color: "rgba(255,255,255,0.75)",
      }}
    >
      <span style={{ color: backendReachable === false ? "#ff6b6b" : "inherit" }}>
        {backendLabel}
      </span>
      {sibylLabel && (
        <span style={{ color: sibylReady === false ? "#ffb020" : "inherit" }}>
          {sibylLabel}
        </span>
      )}
      <span>
        {lastKnownDbSizeBytes !== null
          ? `Sibyl store: ${formatBytes(lastKnownDbSizeBytes)} of ${formatBytes(
              FREE_TIER_CAP_BYTES
            )} (${((lastKnownDbSizeBytes / FREE_TIER_CAP_BYTES) * 100).toFixed(1)}% of free tier) — observed ${
              lastKnownDbSizeCheckedAt ? new Date(lastKnownDbSizeCheckedAt).toLocaleTimeString() : ""
            }`
          : "Sibyl quota: not known yet — observed after your first handoff request"}
      </span>
      <span style={{ marginLeft: "auto", opacity: 0.6 }}>
        {lastCheckedAt ? `Last checked ${new Date(lastCheckedAt).toLocaleTimeString()}` : ""}
      </span>
      <button
        type="button"
        onClick={() => void refresh()}
        disabled={checking}
        style={{
          background: "rgba(255,255,255,0.08)",
          border: "1px solid rgba(255,255,255,0.2)",
          borderRadius: "6px",
          color: "inherit",
          padding: "4px 10px",
          fontSize: "12px",
          cursor: checking ? "default" : "pointer",
        }}
      >
        {checking ? "Refreshing..." : "Refresh status"}
      </button>
    </div>
  );
}
