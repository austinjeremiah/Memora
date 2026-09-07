"use client";

import { ReactNode } from "react";
import type { GateResult } from "@/lib/api/types";
import { Icon, type IconName } from "./Icon";
import AnimatedNumber from "./AnimatedNumber";

/**
 * The app's shared primitives. Styling lives in styles/app.css as tokens
 * lifted from the Framer landing, so the app and marketing site read as one
 * product without importing the landing's generated class names.
 *
 * Every page composes from here. Nothing renders a raw inline style.
 */

export function Card({ children, tight, flush, className = "" }: {
  children: ReactNode; tight?: boolean; flush?: boolean; className?: string;
}) {
  return (
    <div className={`card${tight ? " card--tight" : ""}${flush ? " card--flush" : ""} ${className}`}>
      {children}
    </div>
  );
}

export function Section({ title, action, children }: {
  title: string; action?: ReactNode; children: ReactNode;
}) {
  return (
    <section className="stack">
      <div className="row row--between">
        <h2 className="section-title">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

/** The gate's verdict. Three colours carrying the product's core meaning. */
export function GateBadge({ result }: { result: GateResult }) {
  const map: Record<GateResult, { cls: string; label: string }> = {
    ALLOW: { cls: "badge--allow", label: "ALLOW" },
    NEEDS_REVIEW: { cls: "badge--review", label: "NEEDS REVIEW" },
    BLOCK: { cls: "badge--block", label: "BLOCK" },
  };
  const { cls, label } = map[result];
  return <span className={`badge ${cls}`}>{label}</span>;
}

export function Badge({ children, tone = "neutral" }: {
  children: ReactNode; tone?: "neutral" | "accent" | "allow" | "review" | "block";
}) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

/** The one decorative color per card. Keep it to accent/amber -- the
 * product's own two brand colors -- rather than a rainbow per tile. */
export function IconBadge({ icon, tone = "accent" }: {
  icon: IconName; tone?: "accent" | "amber";
}) {
  return (
    <span className={`icon-badge icon-badge--${tone}`}>
      <Icon name={icon} />
    </span>
  );
}

export function Button({ children, onClick, href, variant = "default", size, disabled, type = "button" }: {
  children: ReactNode; onClick?: () => void; href?: string;
  variant?: "default" | "primary" | "accent" | "ghost";
  size?: "sm"; disabled?: boolean; type?: "button" | "submit";
}) {
  const cls = `btn${variant !== "default" ? ` btn--${variant}` : ""}${size ? ` btn--${size}` : ""}`;
  if (href) return <a className={cls} href={href} target={href.startsWith("http") ? "_blank" : undefined} rel="noreferrer">{children}</a>;
  return <button type={type} className={cls} onClick={onClick} disabled={disabled}>{children}</button>;
}

export function Field({ label, children, hint }: {
  label: string; children: ReactNode; hint?: string;
}) {
  return (
    <div className="field">
      <label className="field__label">{label}</label>
      {children}
      {hint && <span className="dim">{hint}</span>}
    </div>
  );
}

export function Notice({ title, children, tone = "info" }: {
  title?: string; children: ReactNode; tone?: "info" | "error" | "warn";
}) {
  const cls = tone === "error" ? "notice notice--error" : tone === "warn" ? "notice notice--warn" : "notice";
  return (
    <div className={cls} role={tone === "error" ? "alert" : undefined}>
      {title && <p className="notice__title">{title}</p>}
      <div className="subtle">{children}</div>
    </div>
  );
}

/**
 * Sibyl store usage.
 *
 * The cap is NEVER hardcoded here: the backend returns soft_cap_bytes on
 * every response and it has already changed once (the docs said 2 MiB; the
 * real value is 5,242,880). A constant in the frontend would silently go
 * stale again.
 */
export function QuotaMeter({ used, cap, compact }: {
  used: number; cap: number | null; compact?: boolean;
}) {
  const kb = (n: number) => `${(n / 1024).toFixed(0)} KB`;
  if (cap === null) {
    return <span className="dim">{kb(used)} stored · uncapped tier</span>;
  }
  const pct = (used / cap) * 100;
  const fill = pct >= 100 ? "meter__fill--full" : pct >= 80 ? "meter__fill--warn" : "";
  return (
    <div className="stack stack--tight" style={{ minWidth: compact ? 140 : 200 }}>
      <span className="dim">
        Sibyl store {kb(used)} / {kb(cap)} ({pct.toFixed(1)}%)
      </span>
      <div className="meter">
        <div className={`meter__fill ${fill}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}

/** Hashes, ids, LOINC codes — anything that must be read exactly. */
export function Mono({ children, truncate }: { children: string; truncate?: number }) {
  const text = truncate && children.length > truncate
    ? `${children.slice(0, truncate)}…`
    : children;
  return <span className="mono subtle" title={children}>{text}</span>;
}

export function Skeleton({ height = 16, width = "100%" }: { height?: number; width?: string }) {
  return <div className="skeleton" style={{ height, width }} aria-hidden />;
}

export function SkeletonList({ rows = 3 }: { rows?: number }) {
  return (
    <div className="stack stack--tight" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} width={`${90 - i * 12}%`} />
      ))}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <Card>
      <div className="stack stack--tight">
        <p style={{ margin: 0, fontWeight: 600 }}>{title}</p>
        {children && <div className="subtle">{children}</div>}
      </div>
    </Card>
  );
}

export function StatTile({ label, value, hint, icon, tone = "accent" }: {
  label: string; value: ReactNode; hint?: string;
  icon?: IconName; tone?: "accent" | "amber";
}) {
  return (
    <Card tight>
      <div className="stack stack--tight">
        {icon && <IconBadge icon={icon} tone={tone} />}
        <span className="stat__value">
          {typeof value === "number" ? <AnimatedNumber value={value} /> : value}
        </span>
        <span className="stat__label">{label}</span>
        {hint && <span className="dim">{hint}</span>}
      </div>
    </Card>
  );
}

/** Clinical event severity, using the same ramp as gate verdicts. */
export function SeverityDot({ severity }: { severity: string | null }) {
  const colour = severity === "critical" ? "var(--critical)"
    : severity === "warning" ? "var(--warning)" : "var(--info)";
  return (
    <span
      aria-label={severity ?? "info"}
      title={severity ?? "info"}
      style={{ display: "inline-block", width: 7, height: 7, borderRadius: 999, background: colour, flexShrink: 0 }}
    />
  );
}
