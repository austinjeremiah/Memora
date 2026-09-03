"use client";

import { useAppStatus } from "@/lib/api/AppStatusContext";

/**
 * §9.2 of the build doc: readyz reachable but sibyl:false is a distinct
 * condition from the backend being unreachable (handled by BackendGate) —
 * the app shouldn't lock up, but any page that would call /handoff should
 * warn before the user wastes a selection on a request that's guaranteed
 * to fail with a sibyl_unavailable 503.
 */
export default function SibylWarningBanner() {
  const { backendReachable, sibylReady } = useAppStatus();

  if (backendReachable !== true || sibylReady !== false) return null;

  return (
    <p
      style={{
        margin: 0,
        padding: "12px 16px",
        border: "1px solid #ffb020",
        borderRadius: "10px",
        color: "#ffb020",
        fontSize: "13px",
      }}
    >
      Patient memory is currently unavailable — handoff requests will fail until this is
      resolved. You can still make a selection, but expect an error on submit.
    </p>
  );
}
