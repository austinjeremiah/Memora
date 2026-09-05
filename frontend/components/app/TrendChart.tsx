"use client";

import { useId, useState } from "react";

export interface SeriesPoint {
  value: number;
  at: string;
}

/**
 * A retained lab/vital series, drawn at a size worth reading.
 *
 * This is the single most under-used thing in the store. Every `lab_trend`
 * fact carries its full `series` -- five heart-rate readings, two haemoglobins
 * -- and until now the UI drew a 40px sparkline on one page and threw the rest
 * away behind a collapsed disclosure. A falling heart rate over five readings
 * IS the argument for persistent memory; a number is not.
 *
 * Layout rule that matters: every label is HTML positioned by the browser,
 * never SVG text at a hand-computed offset. EvidenceGraph used to place its
 * status label at `name.length * 6.4 + 76` and overlapped the name it followed
 * -- guessing glyph widths cannot be made correct, so nothing here guesses.
 * The SVG holds marks only; the axis furniture sits in a grid around it.
 */
export default function TrendChart({
  series,
  unit,
  direction,
  delta,
  height = 132,
  compact = false,
}: {
  series: SeriesPoint[];
  unit?: string | null;
  direction?: string | null;
  delta?: number | null;
  height?: number;
  compact?: boolean;
}) {
  const gradId = useId().replace(/:/g, "");
  const [hover, setHover] = useState<number | null>(null);

  if (!series || series.length === 0) return null;

  const values = series.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || Math.abs(max) || 1;

  // Pad the domain so a flat line sits mid-box instead of on an edge.
  const lo = min - span * 0.15;
  const hi = max + span * 0.15;

  const W = 100;
  const H = 100;
  const x = (i: number) =>
    series.length === 1 ? W / 2 : (i / (series.length - 1)) * W;
  const y = (v: number) => H - ((v - lo) / (hi - lo)) * H;

  const line = series.map((p, i) => `${x(i).toFixed(2)},${y(p.value).toFixed(2)}`).join(" ");
  const area = `${x(0).toFixed(2)},${H} ${line} ${x(series.length - 1).toFixed(2)},${H}`;

  const stroke =
    direction === "rising" ? "var(--review)"
      : direction === "falling" ? "var(--accent)"
        : "var(--text-secondary)";

  const active = hover ?? series.length - 1;
  const point = series[active];

  return (
    <div className="trend">
      <div className="trend__head">
        <span className="trend__value">
          {point.value}
          {unit ? <span className="trend__unit">{unit}</span> : null}
        </span>
        <span className="trend__at">{point.at}</span>
      </div>

      {/* Always rendered, even when empty. An element that appears only on
          hover changes the card's height, and a grid of cards then jumps as
          the pointer crosses it -- which is exactly what the wrapping flex
          version did. */}
      <div className="trend__status" data-dir={hover !== null ? "hover" : direction ?? "stable"}>
        {hover !== null
          ? `reading ${active + 1} of ${series.length}`
          : delta != null && series.length > 1
            ? `${delta > 0 ? "+" : ""}${delta} over ${series.length} readings`
            : series.length === 1 ? "single reading" : `${series.length} readings`}
      </div>

      <div className="trend__plot" style={{ height }}>
        <span className="trend__ax trend__ax--hi">{fmt(max)}</span>
        <span className="trend__ax trend__ax--lo">{fmt(min)}</span>

        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          className="trend__svg"
          role="img"
          aria-label={
            `${series.length} readings from ${series[0].at} to ${series[series.length - 1].at}, ` +
            `${min} to ${max}${unit ? ` ${unit}` : ""}, ${direction ?? "trend"}`
          }
        >
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity="0.28" />
              <stop offset="100%" stopColor={stroke} stopOpacity="0" />
            </linearGradient>
          </defs>

          {[0.25, 0.5, 0.75].map((g) => (
            <line key={g} x1="0" y1={H * g} x2={W} y2={H * g}
                  stroke="var(--border)" strokeWidth="0.4"
                  vectorEffect="non-scaling-stroke" />
          ))}

          {series.length > 1 && <polygon points={area} fill={`url(#${gradId})`} />}
          {series.length > 1 && (
            <polyline points={line} fill="none" stroke={stroke} strokeWidth="1.6"
                      strokeLinecap="round" strokeLinejoin="round"
                      vectorEffect="non-scaling-stroke" />
          )}

          <line x1={x(active)} y1="0" x2={x(active)} y2={H}
                stroke={stroke} strokeWidth="1" strokeDasharray="3 3"
                opacity={hover === null ? 0 : 0.55}
                vectorEffect="non-scaling-stroke" />

          {series.map((p, i) => (
            <circle key={`${p.at}-${i}`} cx={x(i)} cy={y(p.value)}
                    r={i === active ? 3.4 : 2.2}
                    fill={i === active ? stroke : "var(--bg)"}
                    stroke={stroke} strokeWidth="1.4"
                    vectorEffect="non-scaling-stroke" />
          ))}
        </svg>

        {/* Hover targets: one full-height column per reading, so the whole
            chart is hoverable rather than only the 3px dots. */}
        <div className="trend__hit" onMouseLeave={() => setHover(null)}>
          {series.map((p, i) => (
            <button key={`${p.at}-hit-${i}`} type="button"
                    className="trend__hitcell"
                    aria-label={`${p.value}${unit ? ` ${unit}` : ""} on ${p.at}`}
                    onMouseEnter={() => setHover(i)}
                    onFocus={() => setHover(i)}
                    onBlur={() => setHover(null)} />
          ))}
        </div>
      </div>

      {!compact && (
        <div className="trend__foot">
          <span>{series[0].at}</span>
          <span>{series[series.length - 1].at}</span>
        </div>
      )}
    </div>
  );
}

/** Trim float noise from stored values without lying about integers. */
function fmt(n: number): string {
  if (Number.isInteger(n)) return String(n);
  return String(Math.round(n * 100) / 100);
}
