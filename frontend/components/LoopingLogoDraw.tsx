"use client";

import { useEffect, useState } from "react";
import { SvgTextDraw } from "@/components/svg-text-draw";

/**
 * SvgTextDraw only plays its draw-in once per mount (it's driven by Framer
 * Motion's initial->animate props, not a CSS loop), so repeating it on an
 * interval means remounting the whole component -- the key bump below is
 * what actually restarts the animation every cycle.
 */
export default function LoopingLogoDraw({
  children,
  intervalMs = 7000,
  className,
}: {
  children: string;
  intervalMs?: number;
  className?: string;
}) {
  const [cycle, setCycle] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setCycle((c) => c + 1), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return (
    <SvgTextDraw key={cycle} className={className} stroke="#fff" showEcg>
      {children}
    </SvgTextDraw>
  );
}
