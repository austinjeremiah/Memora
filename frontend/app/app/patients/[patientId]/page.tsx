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
          <div className="grid grid--3">
            <StatTile label="Facts" value={data.fact_count}
                      hint="current state — one row per record" />
            <StatTile label="Journal events" value={data.event_count}
                      hint="append-only history" />
            <StatTile label="Memory version" value={data.memory_version}
                      hint="increments on every write" />
            <Card tight>
              <div className="stack stack--tight">
                <span className="field__label">Sibyl store</span>
                <QuotaMeter used={data.memory.db_size_bytes}
                            cap={data.memory.soft_cap_bytes} />
              </div>
            </Card>
          </div>

          <AskMemory patientId={decoded} />

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
  const real = trends.filter((t) => (t.readings ?? 0) >= 2);
  if (real.length === 0) return null;

  return (
    <Section title={`Lab trajectories — ${real.length} tests with repeat readings`}>
      <p className="dim" style={{ margin: 0 }}>
        A single result is a number. The same store holding every result is a
        trajectory — which is a different clinical fact.
      </p>
      <div className="grid grid--3">
        {real.map((t) => (
          <Card key={t.name} tight>
            <div className="stack stack--tight">
              <div className="row row--between">
                <strong style={{ fontSize: 13 }}>{t.test ?? t.name}</strong>
                <DirectionBadge direction={t.direction} />
              </div>
              <Sparkline series={t.series} />
              <div className="row row--between">
                <span className="dim">
                  {t.latest_value} {t.unit} · {t.readings} readings
                </span>
                {t.delta !== null && (
                  <span className="dim">
                    {t.delta > 0 ? "+" : ""}{t.delta}
                  </span>
                )}
              </div>
              {t.loinc && <span className="dim">LOINC {t.loinc}</span>}
            </div>
          </Card>
        ))}
      </div>
    </Section>
  );
}

function DirectionBadge({ direction }: { direction: string | null }) {
  if (direction === "rising") return <Badge tone="review">↑ rising</Badge>;
  if (direction === "falling") return <Badge tone="accent">↓ falling</Badge>;
  if (direction === "stable") return <Badge>→ stable</Badge>;
  return <Badge>single</Badge>;
}

/** Plain SVG — no chart library for six points. */
function Sparkline({ series }: { series: { value: number; at: string }[] }) {
  if (series.length < 2) return null;
  const values = series.map((p) => p.value);
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  const w = 220, h = 40;
  const points = series.map((p, i) => {
    const x = (i / (series.length - 1)) * w;
    const y = h - ((p.value - min) / span) * (h - 8) - 4;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} role="img"
         aria-label={`${series.length} readings from ${series[0].at} to ${series[series.length - 1].at}`}>
      <polyline points={points} fill="none" stroke="var(--accent)" strokeWidth="1.5"
                strokeLinecap="round" strokeLinejoin="round" />
      {series.map((p, i) => {
        const x = (i / (series.length - 1)) * w;
        const y = h - ((p.value - min) / span) * (h - 8) - 4;
        return <circle key={i} cx={x} cy={y} r="2" fill="var(--accent)" />;
      })}
    </svg>
  );
}

/** WARM state, grouped by kind, with the coding systems visible. */
function Facts({ facts }: { facts: Record<string, StoredFactOut[]> }) {
  const kinds = Object.keys(facts).sort();
  return (
    <Section title="Current facts">
      <div className="stack">
        {kinds.map((kind) => (
          <Card key={kind} tight>
            <details>
              <summary style={{ cursor: "pointer", listStyle: "none" }}>
                <span className="row row--between">
                  <strong>{KIND_LABELS[kind] ?? kind}</strong>
                  <Badge>{facts[kind].length}</Badge>
                </span>
              </summary>
              <div className="scroll-x" style={{ marginTop: 12 }}>
                <table className="table">
                  <thead>
                    <tr><th>Name</th><th>Status</th><th>Detail</th></tr>
                  </thead>
                  <tbody>
                    {facts[kind].map((f) => (
                      <tr key={f.name}>
                        <td><Mono truncate={44}>{f.name}</Mono></td>
                        <td>{f.status && <Badge>{f.status}</Badge>}</td>
                        <td className="subtle">{summarise(f.body)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </Card>
        ))}
      </div>
    </Section>
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
