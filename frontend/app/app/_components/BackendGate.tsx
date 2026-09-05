"use client";

import Link from "next/link";
import { useAppStatus } from "@/lib/api/AppStatusContext";
import { getApiBaseUrl } from "@/lib/api/baseUrl";
import { Card, Notice, SkeletonList } from "@/components/app/ui";

/**
 * Replaces the whole page when the backend cannot be reached at all.
 *
 * Distinct from Sibyl being unavailable: there, the backend answers and says
 * its memory layer is gone, which pages surface as a 503 with an explanation.
 * Here nothing answered, so there is nothing to explain -- and the most likely
 * cause is a wrong API URL or a server that is not running.
 */
export default function BackendGate({ children }: { children: React.ReactNode }) {
  const { backendReachable, checking, refresh } = useAppStatus();

  if (backendReachable === null) {
    return <SkeletonList rows={4} />;
  }

  if (backendReachable === false) {
    return (
      <Card>
        <div className="stack">
          <Notice tone="error" title="Cannot reach the MEMORA backend">
            Nothing answered at <code className="mono">{getApiBaseUrl()}</code>.
            Start it with <code className="mono">scripts/run_api.sh</code>, or point
            the app at a different URL.
          </Notice>
          <div className="row">
            <button type="button" className="btn btn--primary"
                    onClick={() => void refresh()} disabled={checking}>
              {checking ? "Retrying…" : "Retry"}
            </button>
            <Link href="/app/settings" className="btn">Settings</Link>
          </div>
        </div>
      </Card>
    );
  }

  return <>{children}</>;
}
