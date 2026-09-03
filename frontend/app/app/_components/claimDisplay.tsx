"use client";

/**
 * Shared claims-rendering pieces used by both the Handoff Brief page
 * (/app/handoff/result) and Compare Situations (/app/compare). Per the
 * build doc's own §8.1: Compare "reuses the same claims-list component from
 * §6.1, not rebuilt... this keeps the gate-result presentation logic in
 * exactly one place in the codebase." Extracted here after Phase 2/3 so
 * Compare doesn't fork a second copy of it.
 */

import { useState } from "react";
import { ClaimOut, MemoraApiError } from "@/lib/api/types";

export const LOADING_MESSAGES = [
  "Reading patient memory from Sibyl...",
  "Proposing a clinical brief...",
  "Checking every claim against evidence...",
  "Applying the safety gate...",
];

export function errorMessage(e: unknown): { heading: string; body: string } {
  if (e instanceof MemoraApiError) {
    switch (e.code) {
      case "sibyl_unavailable":
        return {
          heading: "Patient memory is currently unavailable",
          body: "No context can be retrieved. This is not retried automatically and nothing is cached — try again once Sibyl is reachable.",
        };
      case "memory_quota_exceeded":
        return {
          heading: "Memory store is at capacity",
          body: "The Sibyl free-tier cap (2,097,152 bytes) has been reached. No further handoff requests can be processed until this is resolved.",
        };
      case "patient_unknown":
        return { heading: "No memory found for this patient", body: e.detail };
      case "llm_unavailable":
        return { heading: "The model provider is unreachable", body: e.detail };
      case "unknown_clinician":
        return {
          heading: "Unknown clinician",
          body: "This should be impossible from the picker — it's a frontend bug if it happens. " + e.detail,
        };
      case "unknown_situation":
        return { heading: "Unknown situation", body: e.detail };
      case "network_error":
        return { heading: "Could not reach the backend", body: e.detail };
      default:
        return { heading: "Something went wrong", body: e.detail };
    }
  }
  return { heading: "Something went wrong", body: e instanceof Error ? e.message : String(e) };
}

const GATE_ORDER: Record<string, number> = { BLOCK: 0, NEEDS_REVIEW: 1, ALLOW: 2 };

export function sortClaims(claims: ClaimOut[]): ClaimOut[] {
  return [...claims].sort((a, b) => (GATE_ORDER[a.gate_result] ?? 3) - (GATE_ORDER[b.gate_result] ?? 3));
}

export function countByGate(claims: ClaimOut[]): { ALLOW: number; BLOCK: number; NEEDS_REVIEW: number } {
  const c = { ALLOW: 0, BLOCK: 0, NEEDS_REVIEW: 0 };
  for (const claim of claims) {
    if (claim.gate_result in c) c[claim.gate_result as keyof typeof c]++;
  }
  return c;
}

export function badgeStyle(gate: string): React.CSSProperties {
  const base: React.CSSProperties = {
    display: "inline-block",
    padding: "4px 12px",
    borderRadius: "999px",
    fontWeight: 700,
    fontSize: "13px",
    letterSpacing: "0.02em",
  };
  if (gate === "ALLOW") return { ...base, background: "#16351f", color: "#4ade80" };
  if (gate === "BLOCK") return { ...base, background: "#3a1414", color: "#ff6b6b" };
  return { ...base, background: "#3a2e10", color: "#ffb020" }; // NEEDS_REVIEW
}

export function ClaimsSummaryBadges({ claims }: { claims: ClaimOut[] }) {
  const counts = countByGate(claims);
  return (
    <div style={{ display: "flex", gap: "10px", fontSize: "13px" }}>
      <span style={badgeStyle("BLOCK")}>{counts.BLOCK} BLOCK</span>
      <span style={badgeStyle("NEEDS_REVIEW")}>{counts.NEEDS_REVIEW} NEEDS_REVIEW</span>
      <span style={badgeStyle("ALLOW")}>{counts.ALLOW} ALLOW</span>
    </div>
  );
}

export function EmptyClaimsMessage() {
  return (
    <p style={{ opacity: 0.75 }}>
      No relevant claims were found for this situation and patient. This can be a
      genuinely correct outcome — it means nothing new surfaced for this specific
      combination, not that something failed.
    </p>
  );
}

/**
 * Approval controls are optional. Omit `interactive` entirely (as Compare
 * does — approve is deliberately not available from that page, per §8.1)
 * and the card renders read-only: badge, text, reason, evidence, nothing
 * selectable.
 */
export interface ClaimCardInteractive {
  selected: boolean;
  confirming: boolean;
  onToggle: () => void;
  onConfirm: () => void;
}

export function ClaimCard({
  claim,
  interactive,
}: {
  claim: ClaimOut;
  interactive?: ClaimCardInteractive;
}) {
  const [expanded, setExpanded] = useState(false);
  const { selected, confirming, onToggle, onConfirm } = interactive ?? {
    selected: false,
    confirming: false,
    onToggle: () => {},
    onConfirm: () => {},
  };

  return (
    <div
      style={{
        border: "1px solid rgba(255,255,255,0.15)",
        borderRadius: "12px",
        padding: "16px 18px",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        opacity: claim.gate_result === "BLOCK" ? 0.75 : 1,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px" }}>
        <span style={badgeStyle(claim.gate_result)}>{claim.gate_result}</span>
        {interactive && claim.gate_result === "ALLOW" && (
          <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px" }}>
            <input type="checkbox" checked={selected} onChange={onToggle} />
            Include in approval
          </label>
        )}
        {interactive && claim.gate_result === "NEEDS_REVIEW" && !confirming && !selected && (
          <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px" }}>
            <input type="checkbox" checked={false} onChange={onToggle} />
            Include in approval
          </label>
        )}
        {interactive && claim.gate_result === "NEEDS_REVIEW" && selected && (
          <span style={{ fontSize: "13px", color: "#4ade80" }}>✓ Confirmed for approval</span>
        )}
      </div>

      <p style={{ margin: 0, fontSize: "16px" }}>{claim.text}</p>
      <p style={{ margin: 0, fontSize: "14px", opacity: 0.75 }}>{claim.reason}</p>

      {interactive && claim.gate_result === "NEEDS_REVIEW" && confirming && (
        <div
          style={{
            border: "1px solid #ffb020",
            borderRadius: "8px",
            padding: "10px 12px",
            fontSize: "13px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <span>This claim requires review before approval — confirm to include it.</span>
          <button
            type="button"
            onClick={onConfirm}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: "none",
              background: "#ffb020",
              color: "#000",
              fontWeight: 600,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            Confirm
          </button>
        </div>
      )}

      <div>
        {claim.source_kind || claim.source_name ? (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            style={{
              background: "none",
              border: "none",
              color: "rgba(255,255,255,0.7)",
              fontSize: "13px",
              padding: 0,
              cursor: "pointer",
              textDecoration: "underline",
            }}
          >
            Evidence: {claim.source_kind}/{claim.source_name}
            {claim.source_events.length > 0 ? ` (${expanded ? "hide" : "show"} ${claim.source_events.length} event(s))` : ""}
          </button>
        ) : (
          <span style={{ fontSize: "13px", opacity: 0.6 }}>Evidence: No supporting record found</span>
        )}
        {expanded && claim.source_events.length > 0 && (
          <ul style={{ margin: "8px 0 0 0", paddingLeft: "18px", fontSize: "13px", opacity: 0.75 }}>
            {claim.source_events.map((ev, i) => (
              <li key={i}>
                [{ev.timestamp}] {ev.event_type}
                {ev.severity ? ` (${ev.severity})` : ""} — {ev.summary}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function ClaimsList({ claims, interactiveFor }: { claims: ClaimOut[]; interactiveFor?: Map<string, ClaimCardInteractive> }) {
  if (claims.length === 0) return <EmptyClaimsMessage />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
      {sortClaims(claims).map((claim, i) => (
        <ClaimCard key={`${claim.text}-${i}`} claim={claim} interactive={interactiveFor?.get(claim.text)} />
      ))}
    </div>
  );
}

export const primaryBtn: React.CSSProperties = {
  padding: "12px 20px",
  borderRadius: "10px",
  border: "none",
  background: "#fff",
  color: "#000",
  fontWeight: 600,
  cursor: "pointer",
};

export const secondaryBtn: React.CSSProperties = {
  padding: "10px 16px",
  borderRadius: "10px",
  border: "1px solid rgba(255,255,255,0.3)",
  background: "transparent",
  color: "#fff",
  cursor: "pointer",
};
