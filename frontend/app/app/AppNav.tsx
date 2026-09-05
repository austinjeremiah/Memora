"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Nav order follows the demo narrative deliberately: look at the memory,
 * then ask it a question, then compare, then watch it watch itself, then
 * sign. A judge clicking straight through in order sees the argument built.
 *
 * A link is added here only once its page actually exists -- shipping a nav
 * entry that 404s is worse than a shorter nav. Patients lands in F4 and
 * Sentinel in F7; both slot into the order below when they do.
 */
const LINKS = [
  { href: "/app", label: "Status" },
  { href: "/app/handoff/new", label: "Handoff" },
  { href: "/app/compare", label: "Compare" },
  { href: "/app/settings", label: "Settings" },
];

export default function AppNav() {
  const pathname = usePathname();

  return (
    <nav className="app-nav">
      <Link href="/" className="app-nav__brand" style={{ color: "inherit", textDecoration: "none" }}>
        MEMORA
      </Link>
      {LINKS.map((link) => {
        const active = link.href === "/app"
          ? pathname === "/app"
          : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`app-nav__link${active ? " app-nav__link--active" : ""}`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
