"use client";

import type { SourceEventOut } from "@/lib/api/types";

/**
 * Why a verdict happened, drawn.
 *
 * This is deliberately NOT a knowledge graph. The whole-patient graph is
 * bipartite and shallow -- 97 entities, max degree 6, dominated by repeated
 * vitals -- so drawing it wholesale would be a hairball that proves nothing.
 * What carries meaning is provenance for ONE claim: the record it cites, the
 * journal events backing it, and the source id tracing each back to its
 * original FHIR resource.
 *
 * Plain SVG. A chart library for a five-node tree would be all cost.
 */
export default function EvidenceGraph({ kind, name, status, events, verdict }: {
  kind: string;
  name: string;
  status: string | null;
  events: SourceEventOut[];
  verdict: "ALLOW" | "NEEDS_REVIEW" | "BLOCK";
}) {
  if (events.length === 0) return null;

  const rowH = 34;
  const top = 26;
  const height = top + events.length * rowH + 30;
  const trunkX = 14;
  const verdictColour =
    verdict === "ALLOW" ? "var(--allow)"
      : verdict === "NEEDS_REVIEW" ? "var(--review)" : "var(--block)";

  return (
    <div className="scroll-x" style={{ marginTop: 4 }}>
      <svg
        width="100%"
        viewBox={`0 0 520 ${height}`}
        style={{ minWidth: 460, maxWidth: 560 }}
        role="img"
        aria-label={`${events.length} source events supporting ${kind}/${name}, verdict ${verdict}`}
      >
        {/* the cited record */}
        <circle cx={trunkX} cy={12} r="4" fill="var(--accent)" />
        <text x={trunkX + 12} y={16} fill="var(--text)" fontSize="12" fontWeight="600">
          {kind}/{name.length > 34 ? `${name.slice(0, 34)}…` : name}
        </text>
        {status && (
          <text x={trunkX + 12} y={16} dx={`${Math.min(name.length, 34) * 6.4 + 76}`}
                fill="var(--text-muted)" fontSize="11">
            [{status}]
          </text>
        )}

        {/* trunk down to the last event */}
        <line x1={trunkX} y1={18} x2={trunkX} y2={top + (events.length - 1) * rowH}
              stroke="var(--border)" strokeWidth="1" />

        {events.map((e, i) => {
          const y = top + i * rowH;
          const critical = e.severity === "critical";
          return (
            <g key={`${e.source_id ?? i}-${i}`}>
              <line x1={trunkX} y1={y} x2={trunkX + 18} y2={y}
                    stroke="var(--border)" strokeWidth="1" />
              <circle cx={trunkX + 18} cy={y} r="3"
                      fill={critical ? "var(--critical)" : "var(--text-muted)"} />
              <text x={trunkX + 30} y={y + 4} fill="var(--text-secondary)" fontSize="11.5">
                {e.event_type}{critical ? " ⚠" : ""}
              </text>
              <text x={300} y={y + 4} fill="var(--text-muted)" fontSize="11"
                    fontFamily="var(--font-mono)">
                {e.timestamp.slice(0, 10)}
              </text>
              <text x={378} y={y + 4} fill="var(--text-muted)" fontSize="10.5"
                    fontFamily="var(--font-mono)">
                {e.source_id ? e.source_id.slice(0, 16) : "—"}
              </text>
            </g>
          );
        })}

        {/* the verdict this evidence produced */}
        <line x1={trunkX} y1={top + (events.length - 1) * rowH}
              x2={trunkX} y2={height - 18}
              stroke="var(--border)" strokeWidth="1" strokeDasharray="2 3" />
        <circle cx={trunkX} cy={height - 14} r="4" fill={verdictColour} />
        <text x={trunkX + 12} y={height - 10} fill={verdictColour}
              fontSize="12" fontWeight="600">
          {verdict === "NEEDS_REVIEW" ? "NEEDS REVIEW" : verdict}
        </text>
      </svg>
    </div>
  );
}
