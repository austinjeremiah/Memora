"use client";

import type { FindingOut } from "@/lib/api/types";

/**
 * Memory contradicting itself, drawn.
 *
 * The reactive path reads WARM facts as current truth and never asks whether
 * the journal agrees with them. Drift asks exactly that — and the picture is
 * the clearest statement of it: what the store says is TRUE NOW on one side,
 * what the store says HAPPENED on the other, and the conflict between them.
 *
 * Both sides came from the same memory. They cannot both be right.
 */
export default function DriftGraph({ finding }: { finding: FindingOut }) {
  const [eventType, eventDate] = (finding.evidence_event ?? "").split("@");
  const w = 560, h = 132;

  return (
    <div className="scroll-x">
      <svg width="100%" viewBox={`0 0 ${w} ${h}`} style={{ minWidth: 480, maxWidth: 620 }}
           role="img"
           aria-label={`${finding.kind}/${finding.name} conflicts with a ${eventType} event`}>
        {/* WARM — what memory says is true now */}
        <text x="0" y="12" fill="var(--text-muted)" fontSize="10.5"
              letterSpacing="0.08em">WARM · TRUE NOW</text>
        <rect x="0" y="20" width="220" height="42" rx="8"
              fill="var(--bg-subtle)" stroke="var(--border)" />
        <text x="12" y="38" fill="var(--text)" fontSize="12" fontWeight="600"
              fontFamily="var(--font-mono)">
          {finding.name.length > 24 ? `${finding.name.slice(0, 24)}…` : finding.name}
        </text>
        <text x="12" y="53" fill="var(--text-muted)" fontSize="11">
          {finding.kind}
        </text>

        {/* the contradiction */}
        <line x1="228" y1="41" x2="330" y2="41" stroke="var(--block)"
              strokeWidth="1.5" strokeDasharray="4 3" />
        <text x="248" y="34" fill="var(--block)" fontSize="11" fontWeight="600">
          contradicts
        </text>
        <g stroke="var(--block)" strokeWidth="1.5">
          <line x1="272" y1="36" x2="284" y2="48" />
          <line x1="284" y1="36" x2="272" y2="48" />
        </g>

        {/* COLD — what memory says happened */}
        <text x="340" y="12" fill="var(--text-muted)" fontSize="10.5"
              letterSpacing="0.08em">COLD · HAPPENED</text>
        <rect x="340" y="20" width="220" height="42" rx="8"
              fill="var(--block-soft)" stroke="var(--block)" />
        <text x="352" y="38" fill="var(--text)" fontSize="12" fontWeight="600">
          {eventType || "conflicting event"}
        </text>
        <text x="352" y="53" fill="var(--text-muted)" fontSize="11"
              fontFamily="var(--font-mono)">
          {eventDate || ""}
        </text>

        {/* both came from the same store */}
        <line x1="110" y1="66" x2="110" y2="88" stroke="var(--border)" strokeWidth="1" />
        <line x1="450" y1="66" x2="450" y2="88" stroke="var(--border)" strokeWidth="1" />
        <line x1="110" y1="88" x2="450" y2="88" stroke="var(--border)" strokeWidth="1" />
        <line x1="280" y1="88" x2="280" y2="102" stroke="var(--border)" strokeWidth="1" />
        <text x="280" y="118" fill="var(--text-muted)" fontSize="11" textAnchor="middle">
          both read from the same patient memory · no model involved
        </text>
      </svg>
    </div>
  );
}
