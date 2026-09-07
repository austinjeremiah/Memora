"use client";
import * as React from "react";
import { motion, SVGMotionProps } from "motion/react";
import { cn } from "@/lib/utils";

export interface SvgTextDrawProps extends Omit<SVGMotionProps<SVGSVGElement>, "children"> {
    children: string;
    delay?: number;
    speed?: number;
    className?: string;
    /** Draws a trailing EKG trace right after the last letter, in the same stroke and the same reveal animation. */
    showEcg?: boolean;
}

// Simple letter path definitions (lowercase letters)
const letterPaths: Record<string, string> = {
    a: "M 10 30 Q 10 10, 25 10 Q 40 10, 40 25 Q 40 40, 25 40 Q 15 40, 10 35 M 40 10 L 40 40",
    b: "M 10 0 L 10 40 M 10 20 Q 10 10, 20 10 Q 30 10, 30 25 Q 30 40, 20 40 Q 10 40, 10 35",
    c: "M 35 15 Q 30 10, 20 10 Q 10 10, 10 25 Q 10 40, 20 40 Q 30 40, 35 35",
    d: "M 40 0 L 40 40 M 40 10 Q 40 10, 25 10 Q 10 10, 10 25 Q 10 40, 25 40 Q 40 40, 40 35",
    e: "M 35 25 L 10 25 Q 10 10, 25 10 Q 40 10, 40 25 Q 40 40, 25 40 Q 10 40, 10 35",
    f: "M 30 5 Q 25 0, 20 0 M 20 0 L 20 40 M 10 15 L 30 15",
    g: "M 40 10 Q 40 10, 25 10 Q 10 10, 10 25 Q 10 40, 25 40 Q 40 40, 40 30 L 40 45 Q 40 50, 25 50",
    h: "M 10 0 L 10 40 M 10 20 Q 10 10, 20 10 Q 30 10, 30 20 L 30 40",
    i: "M 20 5 L 20 8 M 20 15 L 20 40",
    j: "M 25 5 L 25 8 M 25 15 L 25 40 Q 25 50, 15 50",
    k: "M 10 0 L 10 40 M 30 15 L 10 25 L 30 40",
    l: "M 20 0 L 20 40",
    m: "M 10 40 L 10 10 Q 10 10, 17 10 Q 24 10, 24 17 L 24 40 M 24 10 Q 24 10, 31 10 Q 38 10, 38 17 L 38 40",
    n: "M 10 40 L 10 10 Q 10 10, 20 10 Q 30 10, 30 20 L 30 40",
    o: "M 25 10 Q 10 10, 10 25 Q 10 40, 25 40 Q 40 40, 40 25 Q 40 10, 25 10",
    p: "M 10 50 L 10 10 Q 10 10, 20 10 Q 30 10, 30 25 Q 30 40, 20 40 Q 10 40, 10 35",
    q: "M 40 10 Q 40 10, 25 10 Q 10 10, 10 25 Q 10 40, 25 40 Q 40 40, 40 35 L 40 50",
    r: "M 10 40 L 10 10 Q 10 10, 20 10 Q 30 10, 30 15",
    s: "M 35 15 Q 30 10, 20 10 Q 10 10, 10 17 Q 10 25, 30 25 Q 40 25, 40 33 Q 40 40, 20 40 Q 10 40, 10 35",
    t: "M 20 5 L 20 35 Q 20 40, 25 40 M 10 15 L 30 15",
    u: "M 10 10 L 10 30 Q 10 40, 20 40 Q 30 40, 30 30 L 30 10",
    v: "M 10 10 L 20 40 L 30 10",
    w: "M 10 10 L 15 40 L 25 10 L 30 40 L 35 10",
    x: "M 10 10 L 30 40 M 30 10 L 10 40",
    y: "M 10 10 L 20 30 L 30 10 M 20 30 L 20 45 Q 20 50, 10 50",
    z: "M 10 10 L 30 10 L 10 40 L 30 40",
    " ": "",
};

// Every glyph above shares the same ~10-unit left bearing, but their ink
// runs to very different max-x values (e.g. "i" ends at 20, "o" at 40), so a
// flat per-letter slot leaves visibly uneven gaps -- most noticeably around
// narrow letters like "r". Advancing by each glyph's own ink width plus a
// fixed trailing gap keeps the whitespace between letters constant instead.
const GAP = 12;
const letterAdvance: Record<string, number> = {
    a: 40, b: 30, c: 35, d: 40, e: 40, f: 30, g: 40, h: 30, i: 20, j: 25,
    k: 30, l: 20, m: 38, n: 30, o: 40, p: 30, q: 40, r: 30, s: 40, t: 30,
    u: 30, v: 30, w: 35, x: 30, y: 30, z: 30, " ": 20,
};

// A heartbeat trace on a y=38 baseline -- level with the foot of "a"'s own
// trailing stroke (its "M 40 10 L 40 40" segment ends at y=40), so the line
// picks up right where the word's last letter leaves off instead of sitting
// on its own independent baseline. Every vertex is a straight line (no Q
// curves) so the whole trace reads as sharp zig-zag, not a rounded blip.
const ECG_PATH = "M 0 38 L 12 38 L 16 31 L 20 38 L 26 38 L 31 44 L 36 8 L 41 56 L 46 38 L 52 38 L 58 29 L 64 38 L 82 38";
const ECG_WIDTH = 82;

export function SvgTextDraw({
    children,
    className,
    delay = 0,
    speed = 1,
    showEcg = false,
    ...props
}: SvgTextDrawProps) {
    // Convert children to string and lowercase
    const text = String(children).toLowerCase();
    const advances = text.split("").map((c) => (letterAdvance[c] ?? 40) + GAP);
    const textWidth = advances.reduce((sum, w) => sum + w, 0);
    const totalWidth = showEcg ? textWidth + ECG_WIDTH + GAP : textWidth;

    // Higher speed = faster animation (divide duration by speed)
    const calc = (x: number) => x / speed;

    return (
        <motion.svg
            className={cn("h-12", className)}
            xmlns="http://www.w3.org/2000/svg"
            viewBox={`0 0 ${totalWidth} ${showEcg ? 62 : 60}`}
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ opacity: 1 }}
            animate={{ opacity: 1 }}
            {...props}
        >
            <title>{children}</title>
            {text.split("").map((char, index) => {
                const path = letterPaths[char] || "";
                if (!path) return null;

                const xOffset = advances.slice(0, index).reduce((sum, w) => sum + w, 0);
                const charDelay = delay + (index * 0.15) / speed;

                return (
                    <motion.path
                        key={`${char}-${index}`}
                        d={path}
                        transform={`translate(${xOffset}, 0)`}
                        initial={{ pathLength: 0, opacity: 0 }}
                        animate={{ pathLength: 1, opacity: 1 }}
                        transition={{
                            pathLength: {
                                duration: calc(0.5),
                                ease: "easeInOut",
                                delay: calc(charDelay),
                            },
                            opacity: {
                                duration: calc(0.3),
                                delay: calc(charDelay),
                            },
                        }}
                    />
                );
            })}
            {showEcg && (() => {
                // Treated as one more character in the sequence: it starts
                // right where the letters' own per-character delay would
                // have put the next glyph, so the line reads as a
                // continuation of the word drawing itself out, not a
                // separately-timed decoration.
                const ecgDelay = delay + (text.length * 0.15) / speed;
                return (
                    <motion.path
                        key="ecg"
                        d={ECG_PATH}
                        transform={`translate(${textWidth}, 0)`}
                        initial={{ pathLength: 0, opacity: 0 }}
                        animate={{ pathLength: 1, opacity: 1 }}
                        transition={{
                            pathLength: { duration: calc(0.7), ease: "easeInOut", delay: calc(ecgDelay) },
                            opacity: { duration: calc(0.3), delay: calc(ecgDelay) },
                        }}
                    />
                );
            })()}
        </motion.svg>
    );
}
