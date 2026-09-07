"use client";

import Link from "next/link";
import { useAppStatus } from "@/lib/api/AppStatusContext";
import { Button, Card, IconBadge, Notice, QuotaMeter, Section, SkeletonList } from "@/components/app/ui";
import Reveal from "@/components/app/Reveal";

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

      <div className="grid grid--hero">
        <Reveal>
        <Section title="Memory layer">
          <Card>
            {backendReachable === null && <SkeletonList rows={2} />}

            {/* backendReachable === false is handled by BackendGate one level up,
                which replaces this page entirely — no duplicate branch here. */}

            {backendReachable === true && (
              <div className="stack">
                <div className="row" style={{ gap: 12 }}>
                  <IconBadge icon="database" tone="accent" />
                  <div className="stack" style={{ gap: 4 }}>
                    <span style={{ fontWeight: 600 }}>
                      {sibylReady === null
                        ? "Checking Sibyl…"
                        : sibylReady
                          ? "Sibyl memory is ready"
                          : "Sibyl memory is unavailable"}
                    </span>
                    <span className="row" style={{ gap: 6 }}>
                      <span
                        className={sibylReady ? "live-dot" : undefined}
                        style={{
                          width: 7, height: 7, borderRadius: 999,
                          background: sibylReady ? "var(--allow)" : "var(--review)",
                          color: sibylReady ? "var(--allow)" : undefined,
                        }}
                      />
                      <span className="dim">{sibylReady ? "Backend-confirmed" : "Awaiting confirmation"}</span>
                    </span>
                  </div>
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
        </Reveal>

        <Reveal delay={0.12}>
        <Section title="Start here">
          <Card>
            <div className="stack">
              <div className="stack stack--tight">
                <div className="row" style={{ gap: 12 }}>
                  <IconBadge icon="arrowRight" tone="accent" />
                  <div className="stack" style={{ gap: 2 }}>
                    <strong>Run a handoff</strong>
                    <span className="subtle">Recall, propose, verify, gate.</span>
                  </div>
                </div>
                <Button href="/app/handoff/new" variant="primary">New handoff</Button>
              </div>

              <div className="card__divider" />

              <div className="stack stack--tight">
                <div className="row" style={{ gap: 12 }}>
                  <IconBadge icon="columns" tone="amber" />
                  <div className="stack" style={{ gap: 2 }}>
                    <strong>Compare situations</strong>
                    <span className="subtle">Three questions, three answers.</span>
                  </div>
                </div>
                <Button href="/app/compare">Compare</Button>
              </div>
            </div>
          </Card>
        </Section>
        </Reveal>
      </div>

      <p className="dim" style={{ margin: 0 }}>
        Synthetic patient data only — generated with Synthea. Not for clinical use.{" "}
        <Link href="/app/settings" style={{ color: "var(--accent-text)" }}>
          Configure the API endpoint
        </Link>
      </p>
    </div>
  );
}
