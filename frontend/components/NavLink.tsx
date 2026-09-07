"use client";

import { useRef } from "react";
import { gsap } from "gsap";
import { SplitText } from "gsap/SplitText";

if (typeof window !== "undefined") {
  gsap.registerPlugin(SplitText);
}

/**
 * Word-by-word underline reveal on hover, replacing the original static
 * "Underline Wrap" decoration. Same technique as the reference snippet
 * (SplitText into words, animate a background-image line from 0% to 100%
 * width per word, staggered) — retargeted from scroll to hover, and from
 * green to the nav's existing accent blue so it matches the rest of the
 * site instead of introducing a new color.
 */
export default function NavLink({
  href,
  children,
}: {
  href: string;
  children: string;
}) {
  const textRef = useRef<HTMLParagraphElement>(null);
  const splitRef = useRef<SplitText | null>(null);

  const getSplit = () => {
    if (!textRef.current) return null;
    if (!splitRef.current) {
      const split = SplitText.create(textRef.current, { type: "words" });
      split.words.forEach((w) => {
        const el = w as HTMLElement;
        el.style.backgroundImage =
          "linear-gradient(rgb(255, 255, 255), rgb(255, 255, 255))";
        el.style.backgroundPosition = "0 100%";
        el.style.backgroundSize = "0% 2px";
        el.style.backgroundRepeat = "no-repeat";
        el.style.paddingBottom = "2px";
      });
      splitRef.current = split;
    }
    return splitRef.current;
  };

  const onEnter = () => {
    const split = getSplit();
    if (!split) return;
    gsap.to(split.words, {
      backgroundSize: "100% 2px",
      stagger: 0.05,
      duration: 0.2,
      ease: "none",
      overwrite: true,
    });
  };

  const onLeave = () => {
    const split = getSplit();
    if (!split) return;
    gsap.to(split.words, {
      backgroundSize: "0% 2px",
      stagger: 0.03,
      duration: 0.15,
      ease: "none",
      overwrite: true,
    });
  };

  return (
    <a
      className="framer-ttQjC framer-QATJw framer-1vp0xhe framer-v-1vp0xhe framer-j6ho85"
      data-framer-name="Default"
      data-highlight="true"
      href={href}
      tabIndex={0}
      style={{ opacity: "1" }}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
    >
      <div
        className="framer-1gsxzzc"
        data-framer-name="Label"
        data-framer-component-type="RichTextContainer"
        style={
          {
            "--extracted-r6o4lv":
              "var(--token-839225cb-b1fc-470d-a0c2-2eb7fcc590b8, rgb(255, 255, 255))",
            "--framer-link-text-color": "rgb(0, 153, 255)",
            "--framer-link-text-decoration": "underline",
            transform: "none",
            opacity: "1",
          } as React.CSSProperties
        }
      >
        <p
          ref={textRef}
          className="framer-text framer-styles-preset-1p9z0bc"
          data-styles-preset="lW2kM2SoC"
          style={
            {
              "--framer-text-color":
                "var(--extracted-r6o4lv, var(--token-839225cb-b1fc-470d-a0c2-2eb7fcc590b8, rgb(255, 255, 255)))",
            } as React.CSSProperties
          }
        >
          {children}
        </p>
      </div>
    </a>
  );
}
