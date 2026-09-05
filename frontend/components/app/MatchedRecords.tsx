"use client";

import type { MatchedRecordOut } from "@/lib/api/types";
import { Badge } from "./ui";
import TrendChart, { SeriesPoint } from "./TrendChart";

/**
 * What the FTS5 search actually pulled out of Sibyl.
 *
 * This used to be a collapsed `<details>` listing bare `kind/name` strings,
 * which discarded the most substantial thing the API returns: `body` is the
 * COMPLETE stored fact, including a lab trend's full `series`. A question
 * about vitals matches seven records carrying five-point trajectories, and the
 * old UI rendered them as seven lines of grey text.
 *
 * Showing this matters beyond looking better. The answer above is one model's
 * prose; this is the retrieved evidence it was allowed to speak from, so a
 * reader can see the gap between what memory holds and what was said -- which
 * is the whole argument for the gate.
 */
export default function MatchedRecords({ matched }: { matched: MatchedRecordOut[] }) {
  if (matched.length === 0) return null;

  const withSeries = matched.filter((m) => seriesOf(m).length > 0);
  const plain = matched.filter((m) => seriesOf(m).length === 0);

  return (
    <div className="stack">
      {withSeries.length > 0 && (
        <>
          <span className="field__label">
            Retained trajectories — {withSeries.length} of {matched.length} matched
            records carry a full reading history
          </span>
          <div className="match-grid">
            {withSeries.map((m) => (
              <TrendRecord key={`${m.kind}/${m.name}`} record={m} />
            ))}
          </div>
        </>
      )}

      {plain.length > 0 && (
        <>
          <span className="field__label">
            {withSeries.length > 0 ? "Other records matched" : "Records matched"}
          </span>
          <div className="match-grid">
            {plain.map((m) => (
              <PlainRecord key={`${m.kind}/${m.name}`} record={m} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function TrendRecord({ record }: { record: MatchedRecordOut }) {
  const b = body(record);
  const series = seriesOf(record);
  const direction = str(b.direction);
  const unit = str(b.unit);

  return (
    <div className="match">
      <div className="match__head">
        <span className="match__title">{str(b.test) ?? humanise(record.name)}</span>
        <DirectionBadge direction={direction} />
        {record.status && <Badge>{record.status}</Badge>}
      </div>

      <TrendChart
        series={series}
        unit={unit}
        direction={direction}
        delta={num(b.delta)}
      />

      <div className="match__facts">
        <Fact k="readings" v={series.length} />
        {b.latest_at != null && <Fact k="latest" v={str(b.latest_at)} />}
        {b.loinc != null && <Fact k="LOINC" v={str(b.loinc)} />}
        <Fact k="range" v={rangeLabel(series, unit)} />
      </div>

      <span className="match__path">{record.kind}/{record.name}</span>
    </div>
  );
}

function PlainRecord({ record }: { record: MatchedRecordOut }) {
  const b = body(record);
  const facts = Object.entries(b)
    .filter(([k, v]) =>
      !SKIP.has(k) && v !== null && v !== undefined && v !== "" &&
      (typeof v === "string" || typeof v === "number" || typeof v === "boolean"))
    .slice(0, 6);

  return (
    <div className="match">
      <div className="match__head">
        <span className="match__title">{str(b.label) ?? humanise(record.name)}</span>
        {record.status && <Badge tone={record.status === "active" ? "accent" : "neutral"}>
          {record.status}
        </Badge>}
      </div>

      {facts.length > 0 && (
        <div className="match__facts">
          {facts.map(([k, v]) => (
            <Fact key={k} k={k.replace(/_/g, " ")} v={String(v)} />
          ))}
        </div>
      )}

      <span className="match__path">{record.kind}/{record.name}</span>
    </div>
  );
}

function Fact({ k, v }: { k: string; v: string | number | null }) {
  if (v === null) return null;
  return (
    <div className="match__fact">
      <span className="match__k">{k}</span>
      <span className="match__v">{v}</span>
    </div>
  );
}

function DirectionBadge({ direction }: { direction: string | null }) {
  if (direction === "rising") return <Badge tone="review">↑ rising</Badge>;
  if (direction === "falling") return <Badge tone="accent">↓ falling</Badge>;
  if (direction === "stable") return <Badge>→ stable</Badge>;
  return <Badge>single reading</Badge>;
}

// ---------------------------------------------------------------------------
// `body` is typed as `Record<string, unknown> | unknown[] | null` because the
// backend returns the raw stored fact -- so every read below is narrowed
// rather than cast. A wrong assumption here would render "undefined" into a
// clinical panel, which is worse than rendering nothing.
// ---------------------------------------------------------------------------

const SKIP = new Set(["label", "last_seen", "series", "test", "loinc"]);

function body(r: MatchedRecordOut): Record<string, unknown> {
  return r.body && !Array.isArray(r.body) ? r.body : {};
}

function seriesOf(r: MatchedRecordOut): SeriesPoint[] {
  const raw = body(r).series;
  if (!Array.isArray(raw)) return [];
  return raw.filter((p): p is SeriesPoint =>
    !!p && typeof p === "object" &&
    typeof (p as SeriesPoint).value === "number" &&
    typeof (p as SeriesPoint).at === "string");
}

function str(v: unknown): string | null {
  return typeof v === "string" ? v : typeof v === "number" ? String(v) : null;
}

function num(v: unknown): number | null {
  return typeof v === "number" ? v : null;
}

function rangeLabel(series: SeriesPoint[], unit: string | null): string {
  const vs = series.map((p) => p.value);
  const lo = Math.min(...vs), hi = Math.max(...vs);
  const u = unit ? ` ${unit}` : "";
  return lo === hi ? `${lo}${u}` : `${lo} – ${hi}${u}`;
}

function humanise(name: string): string {
  const s = name.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}
