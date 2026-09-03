"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/app", label: "Home" },
  { href: "/app/handoff/new", label: "New Handoff" },
  { href: "/app/compare", label: "Compare Situations" },
  { href: "/app/settings", label: "Settings" },
];

export default function AppNav() {
  const pathname = usePathname();

  return (
    <nav
      style={{
        display: "flex",
        gap: "20px",
        padding: "16px 20px",
        borderBottom: "1px solid rgba(255,255,255,0.12)",
        alignItems: "center",
      }}
    >
      <span style={{ fontWeight: 700, marginRight: "8px" }}>MEMORA</span>
      {LINKS.map((link) => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            style={{
              color: active ? "#fff" : "rgba(255,255,255,0.6)",
              textDecoration: "none",
              fontWeight: active ? 600 : 400,
              borderBottom: active ? "2px solid #fff" : "2px solid transparent",
              paddingBottom: "4px",
            }}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
