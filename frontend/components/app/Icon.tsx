import type { ReactNode } from "react";

/**
 * A small hand-drawn icon set, kept in-repo instead of pulling in an icon
 * library for six shapes. Every path shares the same stroke width and
 * line-cap style so they read as one family.
 */
const COMMON = {
  viewBox: "0 0 24 24",
  fill: "none" as const,
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export type IconName =
  | "database" | "arrowRight" | "columns"
  | "activity" | "user" | "shield" | "seal" | "settings";

const PATHS: Record<IconName, ReactNode> = {
  database: (
    <>
      <ellipse cx="12" cy="5.5" rx="7" ry="2.5" />
      <path d="M5 5.5v6c0 1.38 3.13 2.5 7 2.5s7-1.12 7-2.5v-6" />
      <path d="M5 11.5v6c0 1.38 3.13 2.5 7 2.5s7-1.12 7-2.5v-6" />
    </>
  ),
  arrowRight: (
    <>
      <path d="M4 12h16" />
      <path d="M14 6l6 6-6 6" />
    </>
  ),
  columns: (
    <>
      <rect x="3.5" y="4" width="7" height="16" rx="1.5" />
      <rect x="13.5" y="4" width="7" height="16" rx="1.5" />
    </>
  ),
  activity: <path d="M3 12h4l2-7 4 14 2-7h6" />,
  user: (
    <>
      <circle cx="12" cy="8" r="3.25" />
      <path d="M5 20c0-4 3.13-6.5 7-6.5s7 2.5 7 6.5" />
    </>
  ),
  shield: (
    <path d="M12 3l7 3v5.5c0 4.6-3 7.7-7 9.5-4-1.8-7-4.9-7-9.5V6l7-3z" />
  ),
  seal: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M8.5 12.3l2.3 2.3 4.7-4.9" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2.5v3M12 18.5v3M21.5 12h-3M5.5 12h-3M18.6 5.4l-2.1 2.1M7.5 16.5l-2.1 2.1M18.6 18.6l-2.1-2.1M7.5 7.5L5.4 5.4" />
    </>
  ),
};

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} {...COMMON} aria-hidden="true">
      {PATHS[name]}
    </svg>
  );
}
