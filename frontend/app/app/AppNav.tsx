"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "@/components/app/Icon";
import LoopingLogoDraw from "@/components/LoopingLogoDraw";

/**
 * A fixed left sidebar, glass over the same background video as the rest of
 * the app shell. The wordmark uses BentonSansRE at the landing's own weight
 * so the two navs still read as one product.
 *
 * A link is added here only once its page exists -- shipping a nav entry
 * that 404s is worse than a shorter nav.
 */
const LINKS: { href: string; label: string; icon: IconName }[] = [
  { href: "/app", label: "Status", icon: "activity" },
  { href: "/app/patients", label: "Patients", icon: "user" },
  { href: "/app/handoff/new", label: "Handoff", icon: "arrowRight" },
  { href: "/app/compare", label: "Compare", icon: "columns" },
  { href: "/app/sentinel", label: "Sentinel", icon: "shield" },
  { href: "/app/proof", label: "Proof", icon: "seal" },
  { href: "/app/settings", label: "Settings", icon: "settings" },
];

export default function AppNav() {
  const pathname = usePathname();

  return (
    <nav className="app-sidebar">
      <Link href="/" className="app-sidebar__brand">
        <LoopingLogoDraw className="h-8">MEMORA</LoopingLogoDraw>
      </Link>

      <div className="app-sidebar__links">
        {LINKS.map((link) => {
          const active = link.href === "/app"
            ? pathname === "/app"
            : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-label={link.label}
              aria-current={active ? "page" : undefined}
              className={`app-sidebar__link${active ? " app-sidebar__link--active" : ""}`}
            >
              <Icon name={link.icon} size={18} />
              <span>{link.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
