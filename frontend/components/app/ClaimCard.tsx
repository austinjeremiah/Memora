"use client";

import { useState } from "react";
import type { ClaimOut } from "@/lib/api/types";
import { Badge, Card, GateBadge, Mono } from "./ui";
import EvidenceGraph from "./EvidenceGraph";

/**
 * One model-proposed claim and what the gate decided about it.
 *
 * The verdict is never shown alone. A BLOCK shows why it was refused; an
 * ALLOW or NEEDS_REVIEW shows the record it cites and the journal events
 * behind it. That is the product's actual claim -- evidence-linked output --
 * made visible rather than asserted.
 */
export default function ClaimCard({ claim, selectable, selected, onToggle }: {
  claim: ClaimOut;
  selectable?: boolean;
  selected?: boolean;
  onToggle?: () => void;
}) {
  const [showEvidence, setShowEvidence] = useState(false);
  const blocked = claim.gate_result === "BLOCK";
  const accent =
    claim.gate_result === "ALLOW" ? "var(--allow)"
      : claim.gate_result === "NEEDS_REVIEW" ? "var(--review)" : "var(--block)";

  return (
    <Card tight>
      <div className="stack stack--tight" style={{ borderLeft: `2px solid ${accent}`, paddingLeft: 14 }}>
        <div className="row row--between" style={{ alignItems: "flex-start" }}>
          <span style={{ flex: 1, minWidth: 0, lineHeight: 1.5 }}>{claim.text}</span>
          <GateBadge result={claim.gate_result} />
        </div>

        {blocked ? (
          <p className="subtle" style={{ margin: 0, fontSize: 13 }}>{claim.reason}</p>
        ) : (
          <>
            <div className="row" style={{ gap: 8 }}>
              {claim.source_kind && claim.source_name && (
                <Mono truncate={46}>{`${claim.source_kind}/${claim.source_name}`}</Mono>
              )}
              {claim.fact_status && <Badge>{claim.fact_status}</Badge>}
              {claim.source_events.length > 0 && (
                <button type="button" className="btn btn--ghost btn--sm"
                        onClick={() => setShowEvidence(!showEvidence)}>
                  {showEvidence ? "Hide" : `${claim.source_events.length} source event${claim.source_events.length > 1 ? "s" : ""}`}
                </button>
              )}
            </div>

            {claim.triggered_rules.length > 0 && (
              <div className="row" style={{ gap: 6 }}>
                {claim.triggered_rules.map((r) => (
                  <Badge key={r} tone="review">{r.replace(/_/g, " ")}</Badge>
                ))}
              </div>
            )}

            {showEvidence && claim.source_kind && claim.source_name && (
              <EvidenceGraph
                kind={claim.source_kind}
                name={claim.source_name}
                status={claim.fact_status}
                events={claim.source_events}
                verdict={claim.gate_result}
              />
            )}
          </>
        )}

        {selectable && !blocked && (
          <label className="row" style={{ gap: 8, cursor: "pointer", marginTop: 4 }}>
            <input type="checkbox" checked={!!selected} onChange={onToggle} />
            <span className="dim">
              {claim.gate_result === "NEEDS_REVIEW"
                ? "Include — I have reviewed the flag above"
                : "Include in the approved handover"}
            </span>
          </label>
        )}
      </div>
    </Card>
  );
}

/** Counts across a claim set, in the gate's own colours. */
export function GateSummary({ claims }: { claims: ClaimOut[] }) {
  const counts = claims.reduce(
    (acc, c) => ({ ...acc, [c.gate_result]: (acc[c.gate_result] ?? 0) + 1 }),
    {} as Record<string, number>
  );
  return (
    <div className="row" style={{ gap: 8 }}>
      {counts.ALLOW > 0 && <Badge tone="allow">{counts.ALLOW} allowed</Badge>}
      {counts.NEEDS_REVIEW > 0 && <Badge tone="review">{counts.NEEDS_REVIEW} need review</Badge>}
      {counts.BLOCK > 0 && <Badge tone="block">{counts.BLOCK} blocked</Badge>}
    </div>
  );
}
