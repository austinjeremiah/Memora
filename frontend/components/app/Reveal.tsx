"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

/**
 * A fade-and-rise reveal for whatever block it wraps, played once when the
 * block scrolls into view. The same GSAP + ScrollTrigger pattern the
 * landing page already uses (Products.tsx, Footer.tsx) -- so /app doesn't
 * read as a static form bolted onto an animated marketing site.
 */
export default function Reveal({
  children,
  delay = 0,
}: {
  children: ReactNode;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const ctx = gsap.context(() => {
      gsap.from(ref.current, {
        opacity: 0,
        y: 22,
        duration: 0.7,
        delay,
        ease: "power3.out",
        scrollTrigger: {
          trigger: ref.current,
          start: "top 92%",
          toggleActions: "play none none none",
        },
      });
    });
    return () => ctx.revert();
  }, [delay]);

  return <div ref={ref}>{children}</div>;
}
