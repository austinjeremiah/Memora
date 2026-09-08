"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { getPatientMemory } from "@/lib/api/client";
import { useAppStatus } from "@/lib/api/AppStatusContext";
import {
  MemoraApiError, PatientMemoryOut, StoredEventOut, StoredFactOut, TrendOut,
} from "@/lib/api/types";
import { KIND_LABELS } from "@/lib/config/demo-data";
import AskMemory from "@/components/app/AskMemory";
import SessionBar, { SessionState } from "@/components/app/SessionBar";
import TrendChart from "@/components/app/TrendChart";
import {
  Badge, Button, Card, Mono, Notice, QuotaMeter, Section,
  SeverityDot, SkeletonList, StatTile,
} from "@/components/app/ui";

/**
 * The raw stored record.
 *
 * This is the page that makes "persistent memory" inspectable rather than
 * asserted. It shows what is ACTUALLY in Sibyl — every fact with its coding
 * system, every lab as a trajectory, the whole append-only journal — as
 * opposed to /handoff, which shows one situation's filtered view.
 */
export default function PatientMemoryPage({ params }: {
  params: Promise<{ patientId: string }>;
}) {
  const { patientId } = use(params);
  const decoded = decodeURIComponent(patientId);
  const { reportMemory } = useAppStatus();

  const [data, setData] = useState<PatientMemoryOut | null>(null);
  const [error, setError] = useState<MemoraApiError | null>(null);
  // Held here rather than inside SessionBar so the question box can record
  // into the open thread, and so the clinician is the session's rather than a
  // second, separately-chosen one.
  const [session, setSession] = useState<SessionState | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPatientMemory(decoded)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        reportMemory(d.memory);
      })
      .catch((e) => !cancelled && setError(e as MemoraApiError));
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decoded]);

  return (
    <div className="stack stack--loose">
      <div className="stack stack--tight">
        <Link href="/app/patients" className="dim" style={{ textDecoration: "none" }}>
          ← All patients
        </Link>
        <h1 className="page-title">Patient memory</h1>
        <Mono>{decoded}</Mono>
      </div>

      {error && (
        <Notice tone="error"
                title={error.code === "sibyl_unavailable"
                  ? "MEMORA cannot reach its memory layer"
                  : "Could not load this record"}>
          {error.detail}
        </Notice>
      )}

      {!data && !error && <SkeletonList rows={4} />}

      {data && (
        <>
          <div className="match-grid">
            <StatTile icon="database" label="Facts" value={data.fact_count}
                      hint="current state — one row per record" />
            <StatTile icon="activity" tone="amber" label="Journal events" value={data.event_count}
                      hint="append-only history" />
            <StatTile icon="seal" label="Memory version" value={data.memory_version}
                      hint="increments on every write" />
            <Card tight>
              <div className="stack stack--tight">
                <span className="field__label">Sibyl store</span>
                <QuotaMeter used={data.memory.db_size_bytes}
                            cap={data.memory.soft_cap_bytes} />
              </div>
            </Card>
          </div>

          <SessionBar patientId={decoded} onChange={setSession} />

          <AskMemory patientId={decoded}
                     threadId={session?.thread?.thread_id ?? null}
                     clinicianId={session?.session.clinician_id ?? null} />

          <Trajectories trends={data.trends} />
          <Facts facts={data.facts} />
          <Journal events={data.events} total={data.event_count} />

          <div className="row">
            <Button href={`/app/handoff/new?patientId=${encodeURIComponent(decoded)}`}
                    variant="primary">
              Run a handoff on this patient
            </Button>
            <Button href={`/app/compare?patientId=${encodeURIComponent(decoded)}`}>
              Compare situations
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

/** A single value is a number; the same store holding every value is a trend. */
function Trajectories({ trends }: { trends: TrendOut[] }) {
  const [showFlat, setShowFlat] = useState(false);
  const real = trends.filter((t) => (t.readings ?? 0) >= 2);
  if (real.length === 0) return null;

  // Rank by how far a value actually moved relative to its own scale, so a
  // heart rate that fell 25/min outranks a body height that did not move at
  // all. Showing 25 charts at equal weight is not a summary -- it is the store
  // dumped onto the page, and it buries the two readings worth reading.
  const scored = real
    .map((t) => ({ t, move: relativeMove(t) }))
    .sort((a, b) => b.move - a.move);

  const moving = scored.filter((s) => s.move > 0.02).map((s) => s.t);
  const flat = scored.filter((s) => s.move <= 0.02).map((s) => s.t);
  const shown = showFlat ? [...moving, ...flat] : moving;

  return (
    <Section title={`Lab trajectories — ${moving.length} of ${real.length} tests have moved`}>
      <p className="dim" style={{ margin: 0, maxWidth: 640 }}>
        A single result is a number. The same store holding every result is a
        trajectory — which is a different clinical fact. Ordered by how far each
        value moved against its own scale; {flat.length} unchanged
        {flat.length === 1 ? " test is" : " tests are"} folded away rather than
        given equal weight.
      </p>
      <div className="match-grid">
        {shown.map((t) => (
          <div key={t.name} className="match">
            <div className="match__head">
              <span className="match__title">{t.test ?? t.name}</span>
              <DirectionBadge direction={t.direction} />
            </div>
            <TrendChart series={t.series} unit={t.unit}
                        direction={t.direction} delta={t.delta} height={104} />
            <p className="match__read">{readTrend(t)}</p>
            <div className="match__facts">
              <Fact k="readings" v={t.readings ?? t.series.length} />
              {t.latest_at && <Fact k="latest" v={t.latest_at} />}
              {t.loinc && <Fact k="LOINC" v={t.loinc} />}
            </div>
          </div>
        ))}
      </div>
      {flat.length > 0 && (
        <div>
          <Button onClick={() => setShowFlat(!showFlat)}>
            {showFlat
              ? `Hide ${flat.length} unchanged`
              : `Show ${flat.length} unchanged test${flat.length === 1 ? "" : "s"}`}
          </Button>
        </div>
      )}
    </Section>
  );
}

function Fact({ k, v }: { k: string; v: string | number }) {
  return (
    <div className="match__fact">
      <span className="match__k">{k}</span>
      <span className="match__v">{v}</span>
    </div>
  );
}

/** Movement as a fraction of the value's own scale, so units do not decide rank. */
function relativeMove(t: TrendOut): number {
  const vs = t.series.map((p) => p.value);
  if (vs.length < 2) return 0;
  const lo = Math.min(...vs), hi = Math.max(...vs);
  const base = Math.abs(vs[0]) || 1;
  return (hi - lo) / base;
}

/**
 * The trend in a sentence.
 *
 * Every number here is read off the stored series -- this is the difference
 * between displaying a record and saying what it means, and it is the whole
 * reason a trajectory is worth keeping.
 */
function readTrend(t: TrendOut): string {
  const s = t.series;
  if (s.length < 2) return `Single reading of ${s[0]?.value ?? "—"}${unitOf(t)}.`;
  const first = s[0], last = s[s.length - 1];
  const span = `${first.at} to ${last.at}`;
  const u = unitOf(t);
  if (t.direction === "stable") {
    return `Held at ${last.value}${u} across ${s.length} readings, ${span}.`;
  }
  const verb = t.direction === "rising" ? "Rose" : "Fell";
  return `${verb} from ${first.value}${u} to ${last.value}${u} across ${s.length} readings, ${span}.`;
}

function unitOf(t: TrendOut): string {
  return t.unit ? ` ${t.unit}` : "";
}

function DirectionBadge({ direction }: { direction: string | null }) {
  if (direction === "rising") return <Badge tone="review">↑ rising</Badge>;
  if (direction === "falling") return <Badge tone="accent">↓ falling</Badge>;
  if (direction === "stable") return <Badge>→ stable</Badge>;
  return <Badge>single</Badge>;
}

/** WARM state, grouped by kind, with the coding systems visible. */
function Facts({ facts }: { facts: Record<string, StoredFactOut[]> }) {
  const kinds = Object.keys(facts).sort();
  return (
    <Section title="Current facts">
      <div className="stack">
        {kinds.map((kind) => (
          <FactGroup key={kind} kind={kind} rows={facts[kind]} />
        ))}
      </div>
    </Section>
  );
}

/**
 * One expandable kind.
 *
 * Deliberately NOT `<details>`. That element toggles `display`, so the panel
 * has no intermediate height to animate and snaps open -- and no CSS can fix
 * it from the outside. A controlled disclosure wrapping the body in a grid
 * whose single row animates `0fr -> 1fr` gives the browser two real heights to
 * interpolate between, which is a smooth open AND a smooth close with no
 * animation library and no measured pixel heights to go stale.
 */
function FactGroup({ kind, rows }: { kind: string; rows: StoredFactOut[] }) {
  const [open, setOpen] = useState(false);
  const panelId = `facts-${kind}`;

  return (
    <Card tight>
      <button type="button" className="disclosure" aria-expanded={open}
              aria-controls={panelId} onClick={() => setOpen(!open)}>
        <span className={`disclosure__chev${open ? " disclosure__chev--open" : ""}`}
              aria-hidden="true">
          <svg width="10" height="10" viewBox="0 0 10 10">
            <path d="M3 1.5 L7 5 L3 8.5" fill="none" stroke="currentColor"
                  strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <strong style={{ flex: 1, textAlign: "left" }}>{KIND_LABELS[kind] ?? kind}</strong>
        <Badge>{rows.length}</Badge>
      </button>

      <div id={panelId} className={`disclosure__panel${open ? " disclosure__panel--open" : ""}`}>
        <div className="disclosure__inner">
          <div className="scroll-x" style={{ paddingTop: 12 }}>
            <table className="table">
              <thead>
                <tr><th>Name</th><th>Status</th><th>Detail</th></tr>
              </thead>
              <tbody>
                {rows.map((f) => (
                  <tr key={f.name}>
                    <td><Mono truncate={44}>{f.name}</Mono></td>
                    <td>{f.status && <Badge>{f.status}</Badge>}</td>
                    <td className="subtle">{summarise(f.body)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Card>
  );
}

/** Show the clinically meaningful fields — codes included — not raw JSON. */
function summarise(body: StoredFactOut["body"]): string {
  if (!body || typeof body !== "object" || Array.isArray(body)) return "";
  const b = body as Record<string, unknown>;
  const skip = new Set(["label", "last_seen", "series"]);
  return Object.entries(b)
    .filter(([k, v]) => !skip.has(k) && v !== null && v !== "" &&
                        !(Array.isArray(v) && v.length === 0))
    .slice(0, 5)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
    .join(" · ");
}

/** COLD journal — append-only, newest first. */
function Journal({ events, total }: { events: StoredEventOut[]; total: number }) {
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? events : events.slice(0, 25);

  return (
    <Section
      title={`Journal — ${total} events, append-only`}
      action={events.length > 25 && (
        <Button size="sm" variant="ghost" onClick={() => setShowAll(!showAll)}>
          {showAll ? "Show recent" : `Show all ${events.length}`}
        </Button>
      )}
    >
      <Card flush>
        <div className="scroll-x">
          <table className="table">
            <thead>
              <tr><th /><th>When</th><th>Event</th><th>Record</th><th>Source</th></tr>
            </thead>
            <tbody>
              {shown.map((e, i) => (
                <tr key={`${e.source_id ?? i}-${i}`}>
                  <td><SeverityDot severity={e.severity} /></td>
                  <td className="mono">{e.timestamp.slice(0, 10)}</td>
                  <td>
                    <div className="stack stack--tight">
                      <span>{e.summary}</span>
                      <span className="dim">{e.event_type}</span>
                    </div>
                  </td>
                  <td className="subtle">
                    {e.related_kind && e.related_name
                      ? <Mono truncate={26}>{`${e.related_kind}/${e.related_name}`}</Mono>
                      : <span className="dim">—</span>}
                  </td>
                  <td>{e.source_id ? <Mono truncate={14}>{e.source_id}</Mono>
                                    : <span className="dim">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </Section>
  );
}
