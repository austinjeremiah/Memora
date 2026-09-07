"use client";

import { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";

/**
 * Counts up to its target instead of appearing already-settled -- the
 * numbers on this page come from a live sweep or a live store read, and a
 * count-up is a cheap, honest way to say "this just arrived" without
 * claiming more real-time-ness than the data actually has.
 */
export default function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  const state = useRef({ n: 0 });

  useEffect(() => {
    const obj = state.current;
    const tween = gsap.to(obj, {
      n: value,
      duration: 0.8,
      ease: "power2.out",
      onUpdate: () => setDisplay(Math.round(obj.n)),
    });
    return () => {
      tween.kill();
    };
  }, [value]);

  return <>{display.toLocaleString()}</>;
}
