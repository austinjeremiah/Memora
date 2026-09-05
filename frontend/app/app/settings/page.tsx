"use client";

import { useState } from "react";
import { DEFAULT_API_BASE_URL, getApiBaseUrl, setApiBaseUrl } from "@/lib/api/baseUrl";
import { getHealth } from "@/lib/api/client";
import { SITUATIONS } from "@/lib/config/demo-data";
import { useAppStatus } from "@/lib/api/AppStatusContext";

type TestState = { status: "idle" | "testing" | "ok" | "error"; message?: string; at?: number };

export default function SettingsPage() {
  const [url, setUrl] = useState(() => getApiBaseUrl());
  const [test, setTest] = useState<TestState>({ status: "idle" });
  const { refresh } = useAppStatus();

  const save = () => {
    setApiBaseUrl(url || DEFAULT_API_BASE_URL);
  };

  const testConnection = async () => {
    save();
    setTest({ status: "testing" });
    try {
      await getHealth();
      setTest({ status: "ok", at: Date.now() });
      void refresh();
    } catch (e) {
      setTest({
        status: "error",
        message: e instanceof Error ? e.message : "Could not connect.",
        at: Date.now(),
      });
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <h1 style={{ margin: 0 }}>Settings</h1>

      <section style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        <label htmlFor="api-base-url" style={{ fontSize: "13px", opacity: 0.7 }}>
          API Base URL
        </label>
        <div style={{ display: "flex", gap: "10px" }}>
          <input
            id="api-base-url"
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onBlur={save}
            placeholder={DEFAULT_API_BASE_URL}
            style={{
              flex: 1,
              padding: "10px 12px",
              borderRadius: "8px",
              border: "1px solid rgba(255,255,255,0.25)",
              background: "rgba(255,255,255,0.05)",
              color: "#fff",
            }}
          />
          <button
            type="button"
            onClick={() => void testConnection()}
            disabled={test.status === "testing"}
            style={{
              padding: "10px 16px",
              borderRadius: "8px",
              border: "none",
              background: "#fff",
              color: "#000",
              fontWeight: 600,
              cursor: test.status === "testing" ? "default" : "pointer",
            }}
          >
            {test.status === "testing" ? "Testing..." : "Test Connection"}
          </button>
        </div>

        {test.status === "ok" && (
          <p style={{ margin: 0, color: "#4ade80", fontSize: "13px" }}>
            Connected — {test.at ? new Date(test.at).toLocaleTimeString() : ""}
          </p>
        )}
        {test.status === "error" && (
          <p style={{ margin: 0, color: "#ff6b6b", fontSize: "13px" }}>
            Could not connect to {url || DEFAULT_API_BASE_URL}
            {test.message ? ` — ${test.message}` : ""}
          </p>
        )}
      </section>

      <section
        style={{
          border: "1px solid rgba(255,255,255,0.15)",
          borderRadius: "12px",
          padding: "16px 20px",
          fontSize: "13px",
          opacity: 0.8,
          display: "flex",
          flexDirection: "column",
          gap: "6px",
        }}
      >
        <p style={{ margin: 0 }}>Situations: {SITUATIONS.length} (hardcoded — no backend endpoint exists)</p>
      </section>
    </div>
  );
}
