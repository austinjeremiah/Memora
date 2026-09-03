"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppStatus } from "@/lib/api/AppStatusContext";
import { primaryBtn } from "./claimDisplay";

/**
 * §9.1 of the build doc: if the backend is unreachable, the whole app should
 * degrade to one clear full-screen state, not five individually-broken
 * pages. Settings stays reachable regardless — it's the one place you can
 * actually fix a wrong API base URL, so blocking it here would trap the user.
 */
export default function BackendGate({ children }: { children: React.ReactNode }) {
  const { backendReachable, refresh, checking } = useAppStatus();
  const pathname = usePathname();
  const isSettings = pathname === "/app/settings";

  if (backendReachable === false && !isSettings) {
    return (
      <div
        style={{
          minHeight: "60vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "16px",
          textAlign: "center",
          padding: "60px 20px",
        }}
      >
        <h1 style={{ margin: 0 }}>MEMORA&apos;s backend isn&apos;t reachable right now.</h1>
        <p style={{ opacity: 0.7, maxWidth: "480px", margin: 0 }}>
          Nothing else in this app will work until this is fixed. If you just started the
          backend, it may still be starting up — or the API base URL below may be wrong.
        </p>
        <div style={{ display: "flex", gap: "12px" }}>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={checking}
            style={{ ...primaryBtn, opacity: checking ? 0.6 : 1, cursor: checking ? "default" : "pointer" }}
          >
            {checking ? "Retrying..." : "Retry"}
          </button>
          <Link
            href="/app/settings"
            style={{
              padding: "12px 20px",
              borderRadius: "10px",
              border: "1px solid rgba(255,255,255,0.3)",
              color: "#fff",
              textDecoration: "none",
            }}
          >
            Go to Settings
          </Link>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
