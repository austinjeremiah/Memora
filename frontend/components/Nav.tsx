"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import NavLink from "@/components/NavLink";
import AngularGlowButton from "@/components/AngularGlowButton";

export default function Nav() {
  const logoRef = useRef<HTMLDivElement>(null);
  const linksRef = useRef<HTMLDivElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!logoRef.current || !linksRef.current || !ctaRef.current) return;
    gsap.from(
      [logoRef.current, linksRef.current, ctaRef.current],
      { opacity: 0, y: -40, duration: 2.0, ease: "power3.out" }
    );
  }, []);

  return (
    <>
      <div className="framer-dpe114-container" data-framer-appear-id="dpe114" style={{opacity: "1", transform: "none", willChange: "transform"}}>
        <div className="ssr-variant hidden-1827i6x hidden-9a9x5i">
          <nav className="framer-ZUPdC framer-90tdu2 framer-v-90tdu2" data-framer-name="Desktop" style={{backgroundColor: "rgba(0, 0, 0, 0)", width: "100%", boxShadow: "none", opacity: "1"}}>
            <div className="framer-yq3j0r" data-framer-name="Container" style={{opacity: "1", display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center"}}>
              <div className="framer-1of73k0" data-framer-name="Content" style={{opacity: "1", justifySelf: "start"}}>
                <div ref={logoRef} className="framer-1yvwb09" data-framer-name="Logo" style={{backdropFilter: "none", backgroundColor: "transparent", boxShadow: "none", borderRadius: "0", opacity: "1", width: "210px", minWidth: "210px", overflow: "visible"}}>
                  <a className="framer-c2linv framer-c0tdwz" data-framer-name="Logo Image " href="/" data-framer-page-link-current="true" style={{opacity: "1", display: "flex", alignItems: "center", justifyContent: "center", overflow: "visible"}}>
                    <span style={{fontFamily: "BentonSansRE, Verdana, sans-serif", fontSize: "34px", fontWeight: 400, fontStyle: "normal", lineHeight: "normal", letterSpacing: "normal", color: "rgb(255, 255, 255)", whiteSpace: "nowrap"}}>
                      MEMORA
                    </span>
                  </a>
                </div>
              </div>
              <div ref={linksRef} className="framer-199y88y" data-framer-name="Links" style={{backdropFilter: "blur(8px)", borderRadius: "999px", boxShadow: "inset -3px -2px 8px 0px var(--token-5a7f2bca-ee8c-42c5-80e1-f72de38d4fdf, rgba(255, 255, 255, 0.07))", opacity: "1"}}>
                <nav className="framer-48nfym" data-framer-name="Links" style={{opacity: "1"}}>
                  <div className="framer-ocqhot-container" style={{opacity: "1"}}>
                    <NavLink href="#platform">Platform</NavLink>
                  </div>
                  <div className="framer-1hxdou6-container" style={{opacity: "1"}}>
                    <NavLink href="#how-it-works">About</NavLink>
                  </div>
                  <div className="framer-9hdncu-container" style={{opacity: "1"}}>
                    <NavLink href="#pricing">Pricing</NavLink>
                  </div>
                  <div className="framer-1aui1a1-container" style={{opacity: "1"}}>
                    <NavLink href="https://github.com/austinjeremiah/Memora">
                      Contact
                    </NavLink>
                  </div>
                </nav>
                <div className="framer-s9npw8" data-border="true" data-framer-name="Border" style={{"--border-bottom-width": "0.5px", "--border-color": "var(--token-839225cb-b1fc-470d-a0c2-2eb7fcc590b8, rgb(255, 255, 255))", "--border-left-width": "0.5px", "--border-right-width": "0.5px", "--border-style": "solid", "--border-top-width": "0.5px", backgroundColor: "var(--token-365216f8-7ee6-4f9f-94e0-ca7d584e4354, rgba(255, 254, 250, 0))", mask: "linear-gradient(160deg, rgb(0, 0, 0) 0%, rgba(0, 0, 0, 0) 39%, rgba(0, 0, 0, 0) 69%, rgb(0, 0, 0) 100%)", borderRadius: "999px", opacity: "1"}} />
              </div>
              <div ref={ctaRef} className="framer-1yzb3cd" data-framer-name="Other" style={{opacity: "1", justifySelf: "end"}}>
                <div className="framer-3a23p6-container" style={{opacity: "1"}}>
                  <AngularGlowButton href="/app">Get Started</AngularGlowButton>
                </div>
              </div>
            </div>
          </nav>
        </div>
      </div>
    </>
  );
}
