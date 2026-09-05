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
 * Laid out in HTML rather than SVG. The SVG version positioned its status
 * label at `x + name.length * 6.4 + 76` -- a guess at glyph width that landed
 * inside the record name for anything as long as
 * `acetaminophen_325_mg_oral_tablet`, and clipped the source-id column on
 * narrow screens. Text measurement belongs to the browser; the connectors are
 * CSS pseudo-elements, so a name of any length pushes its neighbours instead
 * of colliding with them.
 */
export default function EvidenceGraph({ kind, name, status, events, verdict }: {
  kind: string;
  name: string;
  status: string | null;
  events: SourceEventOut[];
  verdict: "ALLOW" | "NEEDS_REVIEW" | "BLOCK";
}) {
  if (events.length === 0) return null;

  const colour =
    verdict === "ALLOW" ? "var(--allow)"
      : verdict === "NEEDS_REVIEW" ? "var(--review)" : "var(--block)";

  return (
    <div className="prov">
      <div className="prov__node prov__node--root">
        <span className="prov__name">{kind}/{name}</span>
        {status && <span className="dim" style={{ fontSize: 11 }}>[{status}]</span>}
      </div>

      {events.map((e, i) => (
        <div
          key={`${e.source_id ?? "none"}-${i}`}
          className={`prov__node${e.severity === "critical" ? " prov__node--crit" : ""}`}
          title={e.summary}
        >
          <span className="prov__type">
            {e.event_type}{e.severity === "critical" ? " ⚠" : ""}
          </span>
          <span className="prov__meta">
            <span>{e.timestamp.slice(0, 10)}</span>
            <span>{e.source_id ? e.source_id.slice(0, 18) : "—"}</span>
          </span>
        </div>
      ))}

      <div className="prov__verdict" style={{ color: colour }}>
        {verdict === "NEEDS_REVIEW" ? "NEEDS REVIEW" : verdict}
      </div>
    </div>
  );
}
