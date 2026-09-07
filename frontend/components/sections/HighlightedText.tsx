"use client";

import { useEffect, useRef } from "react";

/**
 * Each word below is its own span carrying a `--stw-i` index (see
 * scrollHighlight.css for the `.stw-word` opacity formula). The scroll
 * handler below only ever writes one CSS variable per frame
 * (`--stw-progress`, on the container) — word count doesn't change how much
 * work happens on scroll.
 */
const WORD_COUNT = 22;

export default function HighlightedText() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let rafId: number | null = null;

    const update = () => {
      rafId = null;
      const rect = el.getBoundingClientRect();
      const vh = window.innerHeight || document.documentElement.clientHeight;
      // Reveal window: word 1 starts lighting up once the block's top has
      // scrolled up to 85% of viewport height; the whole phrase is fully lit
      // by the time its top reaches 25% of viewport height.
      const start = vh * 0.85;
      const end = vh * 0.25;
      const raw = (start - rect.top) / (start - end);
      const progress = Math.min(1, Math.max(0, raw));
      el.style.setProperty("--stw-progress", String(progress));
    };

    const onScroll = () => {
      if (rafId !== null) return;
      rafId = requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, []);

  let i = 0;
  const word = (text: string) => {
    const style = { "--stw-i": i } as React.CSSProperties;
    i += 1;
    return (
      <span className="stw-word" style={style}>
        {text}
      </span>
    );
  };
  const space = <span style={{ display: "inline" }}> </span>;
  const nl = <span style={{ display: "inline" }}>{"\n"}</span>;

  return (
    <>
      <section className="framer-12dukr9" data-framer-name="Highlighted Text">
        <div className="framer-1f572es" data-framer-name="Container">
          <section className="framer-qf22bw" data-framer-name="Text">
            <div className="framer-1dfsb8l-container" data-code-component-plugin-id="84d4c1">
              <div className="ssr-variant hidden-1pkxm8v hidden-zmbq2w">
                <div
                  ref={containerRef}
                  style={{
                    "--stw-total": WORD_COUNT,
                    maxWidth: "100%",
                    width: "100%",
                    wordWrap: "break-word",
                    overflowWrap: "break-word",
                    whiteSpace: "normal",
                    fontFamily: "\"Inter Display\", \"Inter Display Placeholder\", sans-serif",
                    fontSize: "48px",
                    fontStyle: "normal",
                    fontWeight: "400",
                    letterSpacing: "-0.03em",
                    lineHeight: "1.2em",
                    textAlign: "left",
                  } as React.CSSProperties}
                >
                  {word("We")}
                  {space}
                  {word("help")}
                  {space}
                  {word("clinicians")}
                  {space}
                  {word("remember")}
                  {space}
                  {word("every")}
                  {space}
                  {word("patient,")}
                  {space}
                  {word("verify")}
                  {space}
                  {word("every")}
                  {space}
                  {word("claim,")}
                  {space}
                  {word("and")}
                  {space}
                  {word("trust")}
                  {space}
                  {word("every")}
                  {space}
                  {word("handoff.")}
                  {nl}
                  {word("Unlock")}
                  {space}
                  {word("persistent")}
                  {space}
                  {word("memory,")}
                  {space}
                  {word("deterministic")}
                  {space}
                  {word("gates,")}
                  {space}
                  {word("and")}
                  {space}
                  {word("proof")}
                  {space}
                  {word("recorded")}
                  {space}
                  {word("onchain.")}
                  {nl}
                </div>
              </div>
            </div>
          </section>
          <div className="framer-tv03tz" data-framer-name="Illustration">
            <div className="ssr-variant">
              <div className="framer-1orjkhs-container">
                <div className="framer-8RT1L framer-sdvljw framer-v-1irxddl" data-framer-name="Logo 02" data-highlight="true" style={{width: "100%", opacity: "1"}}>
                  <figure className="framer-1r3kcoz" data-framer-name="Logo 1" style={{opacity: "1", willChange: "transform"}}>
                    <div style={{position: "absolute", borderRadius: "inherit", cornerShape: "inherit", top: "0", right: "0", bottom: "0", left: "0"}} data-framer-background-image-wrapper="true">
                      <img decoding="auto" loading="lazy" width="49" height="68" src="/images/rhi83qnhlwfmpfg2vj176ghopo.svg" alt="Health" style={{display: "block", width: "100%", height: "100%", borderRadius: "inherit", cornerShape: "inherit", objectPosition: "center", objectFit: "contain"}} />
                    </div>
                  </figure>
                  <figure className="framer-ntd1b5" data-framer-name="Logo 2" style={{opacity: "0", willChange: "transform"}}>
                    <div style={{position: "absolute", borderRadius: "inherit", cornerShape: "inherit", top: "0", right: "0", bottom: "0", left: "0"}} data-framer-background-image-wrapper="true">
                      <img decoding="auto" loading="lazy" width="49" height="68" src="/images/eulxkhsvgmgm7xiuguu97va5pqo.svg" alt="" style={{display: "block", width: "100%", height: "100%", borderRadius: "inherit", cornerShape: "inherit", objectPosition: "center", objectFit: "contain"}} />
                    </div>
                  </figure>
                  <figure className="framer-1o6q2gn" data-framer-name="Logo 3" style={{opacity: "0", willChange: "transform"}}>
                    <div style={{position: "absolute", borderRadius: "inherit", cornerShape: "inherit", top: "0", right: "0", bottom: "0", left: "0"}} data-framer-background-image-wrapper="true">
                      <img decoding="auto" loading="lazy" width="40" height="68" src="/images/egipk2zspnufip5an5clxonq40.svg" alt="" style={{display: "block", width: "100%", height: "100%", borderRadius: "inherit", cornerShape: "inherit", objectPosition: "center", objectFit: "contain"}} />
                    </div>
                  </figure>
                </div>
              </div>
            </div>
            <div className="ssr-variant">
              <figure className="framer-rkq3o0 stw-orb-spin" data-framer-name="Gradient Circle" style={{opacity: "1", willChange: "transform"}}>
                <div style={{position: "absolute", borderRadius: "inherit", cornerShape: "inherit", top: "0", right: "0", bottom: "0", left: "0"}} data-framer-background-image-wrapper="true">
                  <img decoding="auto" loading="lazy" width="692" height="692" sizes="(min-width: 1200px) max(min(max((min(max(100vw - 80px, 1px), 1200px) - 48px) / 2, 1px), 346px), 1px), (min-width: 810px) and (max-width: 1199.98px) max(min(min(max(100vw - 80px, 1px), 1200px), 346px), 1px), (max-width: 809.98px) max(min(min(max(100vw - 40px, 1px), 1200px), 346px), 1px)" srcSet="/images/emeabgugaj1mrftuh9nccnlosk.webp 512w, /images/emeabgugaj1mrftuh9nccnlosk.webp 692w" src="/images/emeabgugaj1mrftuh9nccnlosk.webp" alt="" style={{display: "block", width: "100%", height: "100%", borderRadius: "inherit", cornerShape: "inherit", objectPosition: "center", objectFit: "cover"}} />
                </div>
              </figure>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
