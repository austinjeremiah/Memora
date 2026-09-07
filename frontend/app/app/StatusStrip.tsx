"use client";

import { useAppStatus } from "@/lib/api/AppStatusContext";
import { QuotaMeter } from "@/components/app/ui";

/**
 * Always-visible truth about whether memory is actually reachable.
 *
 * The store size and its cap both come from the backend. An earlier version
 * hardcoded a 2 MiB cap here, which was the figure in Sibyl's own docs and
 * wrong -- the real cap is 5,242,880 bytes. A frontend constant for a
 * backend fact goes stale silently, so there isn't one any more.
 */
export default function StatusStrip() {
  const {
    backendReachable, sibylReady, checking, lastCheckedAt,
    lastKnownDbSizeBytes, lastKnownCapBytes, refresh,
  } = useAppStatus();

  const dot = (colour: string, live = false) => (
    <span
      className={live ? "live-dot" : undefined}
      style={{ width: 7, height: 7, borderRadius: 999, background: colour, color: colour, display: "inline-block" }}
    />
  );

  return (
    <div className="status-strip">
      <span className="row" style={{ gap: 7 }}>
        {backendReachable === null ? dot("var(--text-dim)")
          : backendReachable ? dot("var(--allow)", true) : dot("var(--block)")}
        {backendReachable === null ? "Checking backend…"
          : backendReachable ? "Backend reachable" : "Backend unreachable"}
      </span>

      {backendReachable === true && (
        <span className="row" style={{ gap: 7 }}>
          {sibylReady === null ? dot("var(--text-dim)")
            : sibylReady ? dot("var(--allow)", true) : dot("var(--review)")}
          {sibylReady === null ? "Sibyl…" : sibylReady ? "Sibyl memory ready" : "Sibyl unavailable"}
        </span>
      )}

      {lastKnownDbSizeBytes !== null ? (
        <QuotaMeter used={lastKnownDbSizeBytes} cap={lastKnownCapBytes} compact />
      ) : (
        <span className="dim">Store size unknown until the first memory read</span>
      )}

      <span style={{ marginLeft: "auto" }} className="dim">
        {lastCheckedAt ? `checked ${new Date(lastCheckedAt).toLocaleTimeString()}` : ""}
      </span>
      <button
        type="button"
        className="btn btn--ghost btn--sm"
        onClick={() => void refresh()}
        disabled={checking}
      >
        {checking ? "Checking…" : "Refresh"}
      </button>
    </div>
  );
}
