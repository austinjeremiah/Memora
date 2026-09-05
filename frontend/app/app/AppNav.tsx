"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * The same floating glass pill the landing page uses: blurred, fully
 * rounded, lifted off the background by an inset highlight rather than a
 * border. The wordmark uses BentonSansRE at the landing's own weight so the
 * two navs read as one product.
 *
 * A link is added here only once its page exists -- shipping a nav entry
 * that 404s is worse than a shorter nav.
 */
const LINKS = [
  { href: "/app", label: "Status" },
  { href: "/app/patients", label: "Patients" },
  { href: "/app/handoff/new", label: "Handoff" },
  { href: "/app/compare", label: "Compare" },
  { href: "/app/sentinel", label: "Sentinel" },
  { href: "/app/settings", label: "Settings" },
];

export default function AppNav() {
  const pathname = usePathname();

  return (
    <nav className="app-nav">
      <Link href="/" className="app-nav__brand">MEMORA</Link>

      <div className="app-nav__inner">
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
      </div>
    </nav>
  );
}
