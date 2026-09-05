"use client";

import Link from "next/link";
import { useAppStatus } from "@/lib/api/AppStatusContext";
import { Button, Card, Notice, QuotaMeter, Section, SkeletonList } from "@/components/app/ui";

/**
 * The first thing a judge sees. It answers one question before anything
 * else: is the memory layer actually alive?
 *
 * That framing is deliberate. MEMORA's whole claim is that it cannot answer
 * without Sibyl, so the app opens by showing whether Sibyl is there rather
 * than by showing a dashboard that would look identical either way.
 */
export default function StatusPage() {
  const { backendReachable, sibylReady, lastKnownDbSizeBytes, lastKnownCapBytes } =
    useAppStatus();

  return (
    <div className="stack stack--loose">
      <div className="stack stack--tight">
        <h1 className="page-title">System status</h1>
        <p className="subtle" style={{ margin: 0, maxWidth: 620 }}>
          Persistent clinical memory with a deterministic safety gate. Every claim an
          AI proposes is checked against real records before a clinician sees it — so
          the first thing worth confirming is that those records are reachable.
        </p>
      </div>

      <Section title="Memory layer">
        <Card>
          {backendReachable === null && <SkeletonList rows={2} />}

          {/* backendReachable === false is handled by BackendGate one level up,
              which replaces this page entirely — no duplicate branch here. */}

          {backendReachable === true && (
            <div className="stack">
              <div className="row" style={{ gap: 10 }}>
                <span
                  style={{
                    width: 8, height: 8, borderRadius: 999,
                    background: sibylReady ? "var(--allow)" : "var(--review)",
                  }}
                />
                <span style={{ fontWeight: 600 }}>
                  {sibylReady === null
                    ? "Checking Sibyl…"
                    : sibylReady
                      ? "Sibyl memory is ready"
                      : "Sibyl memory is unavailable"}
                </span>
              </div>

              {sibylReady === false && (
                <Notice tone="warn" title="Handoffs will refuse, not guess">
                  The backend is up but cannot open its memory store. Every clinical
                  request will return 503 rather than answer from nothing — that
                  refusal is the intended behaviour, not a bug.
                </Notice>
              )}

              {lastKnownDbSizeBytes !== null && (
                <QuotaMeter used={lastKnownDbSizeBytes} cap={lastKnownCapBytes} />
              )}
            </div>
          )}
        </Card>
      </Section>

      <Section title="Start here">
        <div className="grid grid--3">
          <Card tight>
            <div className="stack stack--tight">
              <strong>Run a handoff</strong>
              <span className="subtle">
                Recall, propose, verify, gate. Watch unsourced claims get refused.
              </span>
              <div><Button href="/app/handoff/new" variant="primary">New handoff</Button></div>
            </div>
          </Card>

          <Card tight>
            <div className="stack stack--tight">
              <strong>Compare situations</strong>
              <span className="subtle">
                One patient, one store, three clinical questions — three different
                answers.
              </span>
              <div><Button href="/app/compare">Compare</Button></div>
            </div>
          </Card>
        </div>
      </Section>

      <p className="dim" style={{ margin: 0 }}>
        Synthetic patient data only — generated with Synthea. Not for clinical use.{" "}
        <Link href="/app/settings" style={{ color: "var(--accent-text)" }}>
          Configure the API endpoint
        </Link>
      </p>
    </div>
  );
}
