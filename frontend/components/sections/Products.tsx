"use client";

import { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

const TAB_CONTAINER_CLASSES = [
  "framer-l8lgel-container",
  "framer-z9k0kt-container",
  "framer-ktt34r-container",
];

/**
 * The scrape only ever captured the "ICU to Ward" tab's content -- Framer
 * exports a static snapshot of whichever variant was active, not every
 * variant, so "Pre-Operative" and "Discharge" were clickable-looking pills
 * with nothing behind them. Content for all three lives here now, each
 * situation keeping the same Gate/Attestation cards (the mechanism really is
 * identical across situations) but its own evidence-resolver line, matching
 * what the section's own subtext promises: "its own retrieval plan, gate
 * policy, and evidence set."
 */
const SITUATIONS = [
  {
    tabLabel: "ICU to Ward",
    panelTitle: "ICU-to-Ward Handoff",
    panelSubtext:
      "The flagship demo: a full ICU-to-ward handoff, gated end to end, with a Sentinel finding and an onchain attestation.",
    dashboardImage: "/images/Dashboard_1.png",
    points: [
      "Evidence Resolver — checks every claim against a real record",
      "Deterministic Gate — ALLOW, NEEDS_REVIEW, or BLOCK",
      "EIP-712 Attestation — signed and recorded on Base",
    ],
  },
  {
    tabLabel: "Pre-Operative",
    panelTitle: "Pre-Operative Check",
    panelSubtext:
      "Confirm allergies, medications, and consent before a single incision — the retrieval plan pulls only what a pre-op review needs.",
    dashboardImage: "/images/Dashboard_2.png",
    points: [
      "Consent & Allergy Resolver — checks every claim against the signed record",
      "Deterministic Gate — ALLOW, NEEDS_REVIEW, or BLOCK",
      "EIP-712 Attestation — signed and recorded on Base",
    ],
  },
  {
    tabLabel: "Discharge",
    panelTitle: "Discharge Review",
    panelSubtext:
      "Verify every instruction against the record before a patient walks out the door — medication changes and follow-ups checked against what's actually documented.",
    dashboardImage: "/images/Dashboard_3.png",
    points: [
      "Instruction Resolver — checks every claim against a real record",
      "Deterministic Gate — ALLOW, NEEDS_REVIEW, or BLOCK",
      "EIP-712 Attestation — signed and recorded on Base",
    ],
  },
];

export default function Products() {
  const [activeTab, setActiveTab] = useState(0);
  const cardRefs = useRef<Array<HTMLDivElement | null>>([]);

  useEffect(() => {
    const cards = cardRefs.current.filter(
      (el): el is HTMLDivElement => el !== null
    );
    if (!cards.length) return;
    const ctx = gsap.context(() => {
      gsap.from(cards, {
        x: 100,
        opacity: 0,
        duration: 0.8,
        ease: "power3.out",
        stagger: 0.15,
        scrollTrigger: {
          trigger: cards[0],
          start: "top 85%",
          toggleActions: "play none none none",
        },
      });
    });
    return () => ctx.revert();
  }, []);

  const situation = SITUATIONS[activeTab];

  return (
    <>
      <section className="framer-1c7dtba" data-framer-name="Products">
        <div className="framer-1lluxfm" data-framer-name="Container">
          <div className="framer-1oehg8v" data-framer-name="Heading">
            <div className="ssr-variant">
              <div className="framer-g41hsn-container">
                <div className="framer-KVhPv framer-gh8mro framer-v-gh8mro" data-framer-name="Variant 1" style={{width: "100%", opacity: "1"}}>
                  <div className="framer-iw76gh-container" style={{opacity: "1"}}>
                    <div className="framer-xjRP0 framer-n3Cte framer-bodobx framer-v-bodobx" data-framer-name="Section Tag" style={{borderRadius: "1px", opacity: "1"}}>
                      <figure className="framer-rpd40f" data-framer-name="Image" style={{opacity: "0.8"}}>
                        <div style={{position: "absolute", borderRadius: "inherit", cornerShape: "inherit", top: "0", right: "0", bottom: "0", left: "0"}} data-framer-background-image-wrapper="true">
                          <img decoding="auto" loading="lazy" width="24" height="24" src="/images/mrmuobodk7ttbd9wzjgly9vak.svg" alt="" style={{display: "block", width: "100%", height: "100%", borderRadius: "inherit", cornerShape: "inherit", objectPosition: "center", objectFit: "cover"}} />
                        </div>
                      </figure>
                      <div className="framer-q7ns0q" data-framer-name="FEATURES" data-framer-component-type="RichTextContainer" style={{"--extracted-r6o4lv": "var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(132, 145, 171))", "--framer-paragraph-spacing": "0px", transform: "none", opacity: "1"}}>
                        <p className="framer-text framer-styles-preset-1xv0u9n" data-styles-preset="VsDceC7bv" style={{"--framer-text-color": "var(--extracted-r6o4lv, var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(132, 145, 171)))"}}>
                          SITUATIONS
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="framer-1v7615w" data-framer-name="Line" style={{backgroundColor: "var(--token-f4dc11a3-eab6-45ff-bb5d-90cc77e6a1e2, rgba(125, 164, 255, 0.16))", opacity: "1"}} />
                </div>
              </div>
            </div>
            <div className="framer-1pvddzl" data-framer-name="Title">
              <div className="framer-dvau4j" data-framer-name="Main">
                <div className="framer-1d1afzp" data-framer-name="Alpha Range Technology" data-framer-component-type="RichTextContainer" style={{transform: "none"}}>
                  <h2 className="framer-text framer-styles-preset-mnfyzd" data-styles-preset="muXEgmE57">
                    Three Clinical Situations
                  </h2>
                </div>
              </div>
              <div className="framer-yq5nkb" data-framer-name="Subtext" data-framer-component-type="RichTextContainer" style={{transform: "none"}}>
                <p className="framer-text framer-styles-preset-1xv0u9n" data-styles-preset="VsDceC7bv" style={{"--framer-text-color": "var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(176, 190, 217))"}}>
                  Each situation ships its own retrieval plan, gate policy, and evidence set.
                </p>
              </div>
            </div>
          </div>
          <div className="ssr-variant hidden-1pkxm8v hidden-zmbq2w">
            <div className="framer-1lo5tin-container" style={{willChange: "transform", opacity: "1", transform: "none"}}>
              <div className="framer-vQXea framer-DPpRZ framer-n3Cte framer-fbqx2h framer-v-fbqx2h" data-framer-name="Desktop 1" style={{width: "100%", opacity: "1"}}>
                <div className="framer-17bqpu9" data-framer-name="Switching Tabs" style={{borderRadius: "16px", opacity: "1"}}>
                  {SITUATIONS.map((s, i) => {
                    const active = activeTab === i;
                    return (
                      <div key={s.tabLabel} className={TAB_CONTAINER_CLASSES[i]} style={{opacity: "1"}}>
                        <div
                          className={`framer-JiE0Z framer-n3Cte framer-1oegfg3 ${active ? "framer-v-1oegfg3" : "framer-v-1ktappr"}`}
                          data-border="true"
                          data-framer-name={active ? "Active" : "Default"}
                          data-highlight="true"
                          tabIndex={0}
                          role="tab"
                          aria-selected={active}
                          onClick={() => setActiveTab(i)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setActiveTab(i); }
                          }}
                          style={{
                            "--border-bottom-width": "1px",
                            "--border-color": "var(--token-f4dc11a3-eab6-45ff-bb5d-90cc77e6a1e2, rgba(125, 164, 255, 0.16))",
                            "--border-left-width": "1px",
                            "--border-right-width": "1px",
                            "--border-style": "solid",
                            "--border-top-width": "1px",
                            backgroundColor: active
                              ? "var(--token-839225cb-b1fc-470d-a0c2-2eb7fcc590b8, rgb(255, 255, 255))"
                              : "var(--token-5a7f2bca-ee8c-42c5-80e1-f72de38d4fdf, rgba(255, 255, 255, 0.07))",
                            borderBottomLeftRadius: "999px", borderBottomRightRadius: "999px",
                            borderTopLeftRadius: "999px", borderTopRightRadius: "999px",
                            opacity: "1", cursor: "pointer",
                          } as React.CSSProperties}
                        >
                          <div className="framer-en8xgk" data-framer-name="Marketing" data-framer-component-type="RichTextContainer" style={{
                            "--extracted-r6o4lv": active
                              ? "var(--token-74e333f8-fe87-4945-af87-cae5b7e16c10, rgb(0, 0, 0))"
                              : "var(--token-839225cb-b1fc-470d-a0c2-2eb7fcc590b8, rgb(255, 255, 255))",
                            "--framer-paragraph-spacing": "0px", transform: "none", opacity: "1",
                          } as React.CSSProperties}>
                            <p className="framer-text framer-styles-preset-1xv0u9n" data-styles-preset="VsDceC7bv" style={{"--framer-text-color": "var(--extracted-r6o4lv)"} as React.CSSProperties}>
                              {s.tabLabel}
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="framer-15s68u1" data-border="true" data-framer-name="Content" style={{"--border-bottom-width": "1px", "--border-color": "var(--token-f4dc11a3-eab6-45ff-bb5d-90cc77e6a1e2, rgba(125, 164, 255, 0.16))", "--border-left-width": "1px", "--border-right-width": "1px", "--border-style": "solid", "--border-top-width": "1px", backgroundColor: "var(--token-755749ce-b09f-4a2c-96af-d48ea1c19cb9, rgba(0, 0, 0, 0))", borderRadius: "24px", opacity: "1"}}>
                  <div className="framer-f2x522" data-framer-name="Container" style={{opacity: "1"}}>
                    <div className="framer-zcamkz" data-framer-name="Top" style={{opacity: "1"}}>
                      <div className="framer-io5gss" data-framer-name="Alpha Range Technology" data-framer-component-type="RichTextContainer" style={{"--framer-paragraph-spacing": "0px", transform: "none", opacity: "1"}}>
                        <h4 className="framer-text framer-styles-preset-1c78dmg" data-styles-preset="hVHiYTsnG">
                          {situation.panelTitle}
                        </h4>
                      </div>
                      <div className="framer-1mrygx3" data-framer-name="Subtext" data-framer-component-type="RichTextContainer" style={{"--extracted-r6o4lv": "var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(176, 190, 217))", "--framer-paragraph-spacing": "0px", transform: "none", opacity: "1"}}>
                        <p className="framer-text framer-styles-preset-1xv0u9n" data-styles-preset="VsDceC7bv" style={{"--framer-text-color": "var(--extracted-r6o4lv, var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(176, 190, 217)))"}}>
                          {situation.panelSubtext}
                        </p>
                      </div>
                    </div>
                    <div className="framer-178ty0" data-framer-name="Points" style={{opacity: "1"}}>
                      {situation.points.map((point, i) => (
                        <div key={point} ref={(el) => { cardRefs.current[i] = el; }} className="framer-gn86jh-container" style={{opacity: "1"}}>
                          <div className="framer-oNbXA framer-n3Cte framer-jmdv9y framer-v-9wsqfm" data-framer-name="Big" style={{width: "100%", borderRadius: "12px", opacity: "1"}}>
                            <div className="framer-o1thv5" data-framer-name="Content" style={{opacity: "1"}}>
                              <div className="framer-v3ildb" data-framer-name="Healthcare" data-framer-component-type="RichTextContainer" style={{"--extracted-r6o4lv": "var(--token-7ed67f45-7ffc-4523-9689-9d08f6aa2909, rgb(209, 212, 227))", "--framer-paragraph-spacing": "0px", transform: "none", opacity: "1"}}>
                                <p className="framer-text framer-styles-preset-1xv0u9n" data-styles-preset="VsDceC7bv" style={{"--framer-text-color": "var(--extracted-r6o4lv, var(--token-7ed67f45-7ffc-4523-9689-9d08f6aa2909, rgb(209, 212, 227)))"}}>
                                  {point}
                                </p>
                              </div>
                              <div className="framer-1l4bl6k" data-framer-name="Label" style={{backgroundColor: "var(--token-2765094e-0f8b-477f-9e2a-092fb0171343, rgba(255, 255, 255, 0.1))", borderRadius: "10px", boxShadow: "rgba(255, 255, 255, 0.31) 0px 0px 4px 0px inset", opacity: "1"}}>
                                <div data-framer-component-type="SVG" data-framer-name="SVG" className="framer-vrl8sz" aria-hidden="true" style={{imageRendering: "pixelated", flexShrink: "0", fill: "var(--token-74e333f8-fe87-4945-af87-cae5b7e16c10, rgb(0, 0, 0))", color: "var(--token-74e333f8-fe87-4945-af87-cae5b7e16c10, rgb(0, 0, 0))", opacity: "1"}}>
                                  <div className="svgContainer" style={{width: "100%", height: "100%", aspectRatio: "inherit"}}>
                                    <svg style={{width: "100%", height: "100%"}} viewBox="0 0 15 11" preserveAspectRatio="none" width="100%" height="100%">
                                      <use href="#svg830506521_425" />
                                    </svg>
                                  </div>
                                </div>
                              </div>
                            </div>
                            <div className="framer-35r8qv" data-border="true" data-framer-name="Border" style={{"--border-bottom-width": "1px", "--border-color": "var(--token-f4dc11a3-eab6-45ff-bb5d-90cc77e6a1e2, rgba(125, 164, 255, 0.16))", "--border-left-width": "1px", "--border-right-width": "1px", "--border-style": "solid", "--border-top-width": "1px", backgroundColor: "var(--token-365216f8-7ee6-4f9f-94e0-ca7d584e4354, rgba(255, 254, 250, 0))", borderRadius: "12px", opacity: "1"}} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="framer-19jweer" data-framer-name="Empty" style={{backgroundColor: "var(--token-365216f8-7ee6-4f9f-94e0-ca7d584e4354, rgba(255, 254, 250, 0))", opacity: "1"}} />
                  <figure className="framer-1kpra2s" data-framer-name="Dashboard 1" style={{filter: "drop-shadow(rgba(0, 0, 0, 0.18) -16px 11px 7px)", willChange: "transform", opacity: "1", transform: "none"}}>
                    <div style={{position: "absolute", borderRadius: "inherit", cornerShape: "inherit", top: "0", right: "0", bottom: "0", left: "0"}} data-framer-background-image-wrapper="true">
                      <img decoding="auto" width="2590" height="1664" sizes="(min-width: 1200px) 679.1104px, (min-width: 810px) and (max-width: 1199.98px) calc(min(max(100vw - 80px, 1px), 1200px) - 32px), (max-width: 809.98px) calc(calc(min(max(100vw, 1px), 1200px) - 40px) - 32px)" src={situation.dashboardImage} alt={`${situation.panelTitle} in the MEMORA app`} style={{display: "block", width: "100%", height: "100%", borderRadius: "inherit", cornerShape: "inherit", objectPosition: "center", objectFit: "contain"}} />
                    </div>
                  </figure>
                </div>
              </div>
            </div>
          </div>
          <div className="framer-cqht81" data-framer-name="Product Cards">
            <div className="ssr-variant hidden-zmbq2w">
              <div className="framer-10uwn4v-container" style={{willChange: "transform", opacity: "1", transform: "none"}}>
                <div className="framer-iTboN framer-i1prX framer-n3Cte framer-12wxzf3 framer-v-12wxzf3" data-framer-name="Desktop" style={{width: "100%", opacity: "1"}}>
                  <div className="framer-lrzngz-container" style={{opacity: "1"}}>
                    <div className="framer-Oyows framer-mo5azh framer-v-13843b6" data-framer-name="Small" style={{background: "linear-gradient(40deg, var(--token-40eb5c15-2df6-4cc5-9a1c-8a90a74b480c, rgb(255, 205, 125)) 0%, var(--token-cef4d4a6-9e30-47e6-bc76-f952a48770af, rgb(12, 15, 22)) 45%, var(--token-991642a5-fe69-44f0-a456-0d249f695158, rgb(1, 117, 255)) 100%)", borderRadius: "24px", boxShadow: "rgba(255, 179, 73, 0.25) 0px 6px 24px 0px", opacity: "1"}}>
                      <div className="framer-wj2xpx" data-framer-name="Container" style={{backdropFilter: "none", backgroundColor: "var(--token-cef4d4a6-9e30-47e6-bc76-f952a48770af, rgb(12, 15, 22))", borderRadius: "24px", opacity: "1"}}>
                        <figure className="framer-1153min" style={{opacity: "1"}}>
                          <div style={{position: "absolute", borderRadius: "inherit", cornerShape: "inherit", top: "0", right: "0", bottom: "0", left: "0"}} data-framer-background-image-wrapper="true">
                            <img decoding="auto" loading="lazy" width="24" height="24" src="/images/uhzkcwolsfcygmitzbsv1tljwi.svg" alt="" style={{display: "block", width: "100%", height: "100%", borderRadius: "inherit", cornerShape: "inherit", objectPosition: "center", objectFit: "contain"}} />
                          </div>
                        </figure>
                      </div>
                    </div>
                  </div>
                  <div className="framer-1ww7ps4" data-framer-name="Label" style={{opacity: "1"}}>
                    <div className="framer-ex0bwp" data-framer-name="Title" data-framer-component-type="RichTextContainer" style={{"--framer-paragraph-spacing": "0px", transform: "none", opacity: "1"}}>
                      <h4 className="framer-text framer-styles-preset-57if0j" data-styles-preset="jMKRHn13U">
                        Pre-Operative
                      </h4>
                    </div>
                    <div className="framer-1cdar5d" data-framer-name="Subtext" data-framer-component-type="RichTextContainer" style={{"--extracted-r6o4lv": "var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(132, 145, 171))", "--framer-paragraph-spacing": "0px", transform: "none", opacity: "1"}}>
                      <p className="framer-text framer-styles-preset-1xv0u9n" data-styles-preset="VsDceC7bv" style={{"--framer-text-color": "var(--extracted-r6o4lv, var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(132, 145, 171)))"}}>
                        Confirm allergies, medications, and consent before a single incision.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="ssr-variant hidden-zmbq2w">
              <div className="framer-10xs4rw-container" style={{willChange: "transform", opacity: "1", transform: "none"}}>
                <div className="framer-iTboN framer-i1prX framer-n3Cte framer-12wxzf3 framer-v-12wxzf3" data-framer-name="Desktop" style={{width: "100%", opacity: "1"}}>
                  <div className="framer-lrzngz-container" style={{opacity: "1"}}>
                    <div className="framer-Oyows framer-mo5azh framer-v-13843b6" data-framer-name="Small" style={{background: "linear-gradient(40deg, var(--token-40eb5c15-2df6-4cc5-9a1c-8a90a74b480c, rgb(255, 205, 125)) 0%, var(--token-cef4d4a6-9e30-47e6-bc76-f952a48770af, rgb(12, 15, 22)) 45%, var(--token-991642a5-fe69-44f0-a456-0d249f695158, rgb(1, 117, 255)) 100%)", borderRadius: "24px", boxShadow: "rgba(255, 179, 73, 0.25) 0px 6px 24px 0px", opacity: "1"}}>
                      <div className="framer-wj2xpx" data-framer-name="Container" style={{backdropFilter: "none", backgroundColor: "var(--token-cef4d4a6-9e30-47e6-bc76-f952a48770af, rgb(12, 15, 22))", borderRadius: "24px", opacity: "1"}}>
                        <figure className="framer-1153min" style={{opacity: "1"}}>
                          <div style={{position: "absolute", borderRadius: "inherit", cornerShape: "inherit", top: "0", right: "0", bottom: "0", left: "0"}} data-framer-background-image-wrapper="true">
                            <img decoding="auto" loading="lazy" width="24" height="24" src="/images/xjqcmhyjo6jeuuatw7enj6rnz0.svg" alt="" style={{display: "block", width: "100%", height: "100%", borderRadius: "inherit", cornerShape: "inherit", objectPosition: "center", objectFit: "contain"}} />
                          </div>
                        </figure>
                      </div>
                    </div>
                  </div>
                  <div className="framer-1ww7ps4" data-framer-name="Label" style={{opacity: "1"}}>
                    <div className="framer-ex0bwp" data-framer-name="Title" data-framer-component-type="RichTextContainer" style={{"--framer-paragraph-spacing": "0px", transform: "none", opacity: "1"}}>
                      <h4 className="framer-text framer-styles-preset-57if0j" data-styles-preset="jMKRHn13U">
                        Discharge
                      </h4>
                    </div>
                    <div className="framer-1cdar5d" data-framer-name="Subtext" data-framer-component-type="RichTextContainer" style={{"--extracted-r6o4lv": "var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(132, 145, 171))", "--framer-paragraph-spacing": "0px", transform: "none", opacity: "1"}}>
                      <p className="framer-text framer-styles-preset-1xv0u9n" data-styles-preset="VsDceC7bv" style={{"--framer-text-color": "var(--extracted-r6o4lv, var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(132, 145, 171)))"}}>
                        Verify every instruction against the record before a patient walks out the door.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="ssr-variant hidden-zmbq2w">
              <div className="framer-1mio07n-container" style={{willChange: "transform", opacity: "1", transform: "none"}}>
                <div className="framer-iTboN framer-i1prX framer-n3Cte framer-12wxzf3 framer-v-12wxzf3" data-framer-name="Desktop" style={{width: "100%", opacity: "1"}}>
                  <div className="framer-lrzngz-container" style={{opacity: "1"}}>
                    <div className="framer-Oyows framer-mo5azh framer-v-13843b6" data-framer-name="Small" style={{background: "linear-gradient(40deg, var(--token-40eb5c15-2df6-4cc5-9a1c-8a90a74b480c, rgb(255, 205, 125)) 0%, var(--token-cef4d4a6-9e30-47e6-bc76-f952a48770af, rgb(12, 15, 22)) 45%, var(--token-991642a5-fe69-44f0-a456-0d249f695158, rgb(1, 117, 255)) 100%)", borderRadius: "24px", boxShadow: "rgba(255, 179, 73, 0.25) 0px 6px 24px 0px", opacity: "1"}}>
                      <div className="framer-wj2xpx" data-framer-name="Container" style={{backdropFilter: "none", backgroundColor: "var(--token-cef4d4a6-9e30-47e6-bc76-f952a48770af, rgb(12, 15, 22))", borderRadius: "24px", opacity: "1"}}>
                        <figure className="framer-1153min" style={{opacity: "1"}}>
                          <div style={{position: "absolute", borderRadius: "inherit", cornerShape: "inherit", top: "0", right: "0", bottom: "0", left: "0"}} data-framer-background-image-wrapper="true">
                            <img decoding="auto" loading="lazy" width="24" height="24" src="/images/g03jloh8ifvewvrxtl5o92ynwi.svg" alt="" style={{display: "block", width: "100%", height: "100%", borderRadius: "inherit", cornerShape: "inherit", objectPosition: "center", objectFit: "contain"}} />
                          </div>
                        </figure>
                      </div>
                    </div>
                  </div>
                  <div className="framer-1ww7ps4" data-framer-name="Label" style={{opacity: "1"}}>
                    <div className="framer-ex0bwp" data-framer-name="Title" data-framer-component-type="RichTextContainer" style={{"--framer-paragraph-spacing": "0px", transform: "none", opacity: "1"}}>
                      <h4 className="framer-text framer-styles-preset-57if0j" data-styles-preset="jMKRHn13U">
                        Sentinel
                      </h4>
                    </div>
                    <div className="framer-1cdar5d" data-framer-name="Subtext" data-framer-component-type="RichTextContainer" style={{"--extracted-r6o4lv": "var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(132, 145, 171))", "--framer-paragraph-spacing": "0px", transform: "none", opacity: "1"}}>
                      <p className="framer-text framer-styles-preset-1xv0u9n" data-styles-preset="VsDceC7bv" style={{"--framer-text-color": "var(--extracted-r6o4lv, var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(132, 145, 171)))"}}>
                        Proactive drift detection running as a safety net between reviews.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="ssr-variant hidden-zmbq2w">
              <div className="framer-1mtjkt1-container" style={{willChange: "transform", opacity: "1", transform: "none"}}>
                <div className="framer-iTboN framer-i1prX framer-n3Cte framer-12wxzf3 framer-v-12wxzf3" data-framer-name="Desktop" style={{width: "100%", opacity: "1"}}>
                  <div className="framer-lrzngz-container" style={{opacity: "1"}}>
                    <div className="framer-Oyows framer-mo5azh framer-v-13843b6" data-framer-name="Small" style={{background: "linear-gradient(40deg, var(--token-40eb5c15-2df6-4cc5-9a1c-8a90a74b480c, rgb(255, 205, 125)) 0%, var(--token-cef4d4a6-9e30-47e6-bc76-f952a48770af, rgb(12, 15, 22)) 45%, var(--token-991642a5-fe69-44f0-a456-0d249f695158, rgb(1, 117, 255)) 100%)", borderRadius: "24px", boxShadow: "rgba(255, 179, 73, 0.25) 0px 6px 24px 0px", opacity: "1"}}>
                      <div className="framer-wj2xpx" data-framer-name="Container" style={{backdropFilter: "none", backgroundColor: "var(--token-cef4d4a6-9e30-47e6-bc76-f952a48770af, rgb(12, 15, 22))", borderRadius: "24px", opacity: "1"}}>
                        <figure className="framer-1153min" style={{opacity: "1"}}>
                          <div style={{position: "absolute", borderRadius: "inherit", cornerShape: "inherit", top: "0", right: "0", bottom: "0", left: "0"}} data-framer-background-image-wrapper="true">
                            <img decoding="auto" loading="lazy" width="24" height="24" src="/images/s0lerkmxkn90kjpse58uwi0gmwa.svg" alt="" style={{display: "block", width: "100%", height: "100%", borderRadius: "inherit", cornerShape: "inherit", objectPosition: "center", objectFit: "contain"}} />
                          </div>
                        </figure>
                      </div>
                    </div>
                  </div>
                  <div className="framer-1ww7ps4" data-framer-name="Label" style={{opacity: "1"}}>
                    <div className="framer-ex0bwp" data-framer-name="Title" data-framer-component-type="RichTextContainer" style={{"--framer-paragraph-spacing": "0px", transform: "none", opacity: "1"}}>
                      <h4 className="framer-text framer-styles-preset-57if0j" data-styles-preset="jMKRHn13U">
                        Attestation
                      </h4>
                    </div>
                    <div className="framer-1cdar5d" data-framer-name="Subtext" data-framer-component-type="RichTextContainer" style={{"--extracted-r6o4lv": "var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(132, 145, 171))", "--framer-paragraph-spacing": "0px", transform: "none", opacity: "1"}}>
                      <p className="framer-text framer-styles-preset-1xv0u9n" data-styles-preset="VsDceC7bv" style={{"--framer-text-color": "var(--extracted-r6o4lv, var(--token-e77749d5-1f11-472b-b926-5090d7e5b50e, rgb(132, 145, 171)))"}}>
                        Clinician-signed, replay-protected, tamper-evident — on Base Sepolia.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <figure className="framer-rd6509" data-framer-name="Bg Gradient">
          <div style={{position: "absolute", borderRadius: "inherit", cornerShape: "inherit", top: "0", right: "0", bottom: "0", left: "0"}} data-framer-background-image-wrapper="true">
            <img decoding="auto" loading="lazy" width="3296" height="2255" sizes="(min-width: 1200px) max(calc(100vw + 702px), 2058px), (min-width: 810px) and (max-width: 1199.98px) max(calc(100vw + 702px), 2058px), (max-width: 809.98px) max(calc(100vw + 702px), 100vw)" srcSet="/images/peuuuxyckhxt8g82fn4y0lpz5s.png 512w, /images/peuuuxyckhxt8g82fn4y0lpz5s.png 1024w, /images/peuuuxyckhxt8g82fn4y0lpz5s.png 2048w, /images/peuuuxyckhxt8g82fn4y0lpz5s.png 3296w" src="/images/peuuuxyckhxt8g82fn4y0lpz5s.png" alt="" style={{display: "block", width: "100%", height: "100%", borderRadius: "inherit", cornerShape: "inherit", objectPosition: "center", objectFit: "contain"}} />
          </div>
        </figure>
      </section>
    </>
  );
}
