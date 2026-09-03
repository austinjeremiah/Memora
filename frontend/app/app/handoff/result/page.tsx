"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { approveHandoff, requestHandoff } from "@/lib/api/client";
import { useAppStatus } from "@/lib/api/AppStatusContext";
import { ApproveClaimIn, ClaimOut, CommitmentOut, HandoffOut, Situation } from "@/lib/api/types";
import {
  ClaimCardInteractive,
  ClaimsList,
  ClaimsSummaryBadges,
  LOADING_MESSAGES,
  errorMessage,
  primaryBtn,
  secondaryBtn,
} from "@/app/app/_components/claimDisplay";

export default function HandoffResultPage() {
  return (
    <Suspense fallback={<p style={{ opacity: 0.6 }}>Loading...</p>}>
      <HandoffResultInner />
    </Suspense>
  );
}

function HandoffResultInner() {
  const params = useSearchParams();
  const { reportDbSize } = useAppStatus();

  const patientId = params.get("patientId") ?? "";
  const situation = (params.get("situation") ?? "") as Situation | "";
  const clinicianId = params.get("clinicianId") ?? "";

  const [status, setStatus] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [response, setResponse] = useState<HandoffOut | null>(null);
  const [error, setError] = useState<{ heading: string; body: string } | null>(null);
  const [messageIndex, setMessageIndex] = useState(0);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmingReview, setConfirmingReview] = useState<Set<string>>(new Set());

  const [approveStatus, setApproveStatus] = useState<"idle" | "submitting" | "done" | "error">("idle");
  const [approveError, setApproveError] = useState<{ heading: string; body: string } | null>(null);
  const [commitment, setCommitment] = useState<CommitmentOut | null>(null);

  const missingSelection = !patientId || !situation || !clinicianId;

  const run = () => {
    if (missingSelection) return;
    setStatus("loading");
    setError(null);
    setResponse(null);
    setSelected(new Set());
    setConfirmingReview(new Set());
    setApproveStatus("idle");
    setApproveError(null);
    setCommitment(null);

    requestHandoff({ patient_id: patientId, situation: situation as Situation, clinician_id: clinicianId })
      .then((res) => {
        setResponse(res);
        setStatus("loaded");
        reportDbSize(res.memory.db_size_bytes);
      })
      .catch((e) => {
        setError(errorMessage(e));
        setStatus("error");
      });
  };

  const didFire = useRef(false);
  useEffect(() => {
    if (didFire.current) return;
    didFire.current = true;
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (status !== "loading") return;
    const id = setInterval(() => {
      setMessageIndex((i) => (i + 1) % LOADING_MESSAGES.length);
    }, 1700);
    return () => clearInterval(id);
  }, [status]);

  const toggleClaim = (claim: ClaimOut) => {
    if (claim.gate_result === "BLOCK") return;
    if (claim.gate_result === "NEEDS_REVIEW" && !selected.has(claim.text)) {
      setConfirmingReview((prev) => new Set(prev).add(claim.text));
      return;
    }
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(claim.text)) next.delete(claim.text);
      else next.add(claim.text);
      return next;
    });
  };

  const confirmReview = (claim: ClaimOut) => {
    setSelected((prev) => new Set(prev).add(claim.text));
    setConfirmingReview((prev) => {
      const next = new Set(prev);
      next.delete(claim.text);
      return next;
    });
  };

  const interactiveFor = useMemo(() => {
    const map = new Map<string, ClaimCardInteractive>();
    for (const claim of response?.claims ?? []) {
      map.set(claim.text, {
        selected: selected.has(claim.text),
        confirming: confirmingReview.has(claim.text),
        onToggle: () => toggleClaim(claim),
        onConfirm: () => confirmReview(claim),
      });
    }
    return map;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [response, selected, confirmingReview]);

  const submitApproval = () => {
    if (!response || selected.size === 0 || approveStatus === "submitting") return;
    setApproveStatus("submitting");
    setApproveError(null);

    const claims: ApproveClaimIn[] = response.claims
      .filter((c) => selected.has(c.text))
      .map((c) => ({ text: c.text, related_kind: c.source_kind, related_name: c.source_name }));

    approveHandoff(patientId, {
      patient_id: patientId,
      situation: situation as Situation,
      clinician_id: clinicianId,
      claims,
    })
      .then((res) => {
        setCommitment(res);
        setApproveStatus("done");
      })
      .catch((e) => {
        setApproveError(errorMessage(e));
        setApproveStatus("error");
      });
  };

  if (missingSelection) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <h1 style={{ margin: 0 }}>Handoff Brief</h1>
        <p style={{ opacity: 0.75 }}>No handoff request in progress.</p>
        <Link href="/app/handoff/new" style={{ color: "#fff" }}>
          Start a Handoff →
        </Link>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {status === "loading" && (
        <section style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <h1 style={{ margin: 0 }}>Handoff Brief</h1>
          <p style={{ opacity: 0.75 }}>{LOADING_MESSAGES[messageIndex]}</p>
        </section>
      )}

      {status === "error" && error && (
        <section
          style={{
            border: "1px solid #ff6b6b",
            borderRadius: "12px",
            padding: "20px",
            display: "flex",
            flexDirection: "column",
            gap: "10px",
          }}
        >
          <h2 style={{ margin: 0, color: "#ff6b6b" }}>{error.heading}</h2>
          <p style={{ margin: 0, opacity: 0.85 }}>{error.body}</p>
          <div style={{ display: "flex", gap: "10px" }}>
            <button type="button" onClick={run} style={primaryBtn}>
              Try again
            </button>
            <Link href="/app/handoff/new" style={{ color: "#fff", alignSelf: "center" }}>
              Change selection
            </Link>
          </div>
        </section>
      )}

      {status === "loaded" && response && (
        <>
          <header>
            <h1 style={{ margin: "0 0 6px 0" }}>Handoff Brief</h1>
            <p style={{ margin: 0, opacity: 0.7 }}>
              Patient {response.patient_id} · {response.situation} · {response.clinician.name} (
              {response.clinician.role})
            </p>
            <p style={{ margin: "4px 0 0 0", opacity: 0.5, fontSize: "13px" }}>
              Task: {response.task} · Model: {response.model} · {response.proposed_count} claim(s) proposed
            </p>
          </header>

          <ClaimsSummaryBadges claims={response.claims} />

          <ClaimsList claims={response.claims} interactiveFor={interactiveFor} />

          <p style={{ fontSize: "13px", opacity: 0.6, margin: 0 }}>
            Sibyl store: {response.memory.db_size_bytes} bytes
            {response.memory.pct_used !== null ? ` (${response.memory.pct_used.toFixed(1)}% of free tier)` : ""}
          </p>

          <div style={{ display: "flex", gap: "12px" }}>
            <button type="button" onClick={run} style={secondaryBtn}>
              Run this situation again
            </button>
            <Link href="/app/handoff/new" style={{ ...secondaryBtn, textDecoration: "none", display: "inline-block" }}>
              Start a different handoff
            </Link>
          </div>

          {response.claims.length > 0 && (
            <section
              style={{
                borderTop: "1px solid rgba(255,255,255,0.15)",
                paddingTop: "20px",
                display: "flex",
                flexDirection: "column",
                gap: "14px",
              }}
            >
              <h2 style={{ margin: 0 }}>Approve &amp; Commit</h2>

              {approveStatus !== "done" && (
                <>
                  <p style={{ margin: 0, opacity: 0.75 }}>
                    {selected.size === 0
                      ? "No claims selected for approval yet."
                      : `${selected.size} claim(s) selected for approval.`}
                  </p>
                  {approveStatus === "submitting" && (
                    <p style={{ margin: 0, color: "#ffb020" }}>
                      Committing to Base Sepolia — this creates a real onchain transaction and
                      may take a few seconds.
                    </p>
                  )}
                  {approveStatus === "error" && approveError && (
                    <div
                      style={{
                        border: "1px solid #ff6b6b",
                        borderRadius: "10px",
                        padding: "14px 16px",
                      }}
                    >
                      <p style={{ margin: "0 0 4px 0", color: "#ff6b6b", fontWeight: 600 }}>
                        {approveError.heading}
                      </p>
                      <p style={{ margin: 0, opacity: 0.85, fontSize: "14px" }}>
                        {approveError.body} No claims were approved — the clinical content
                        itself is unaffected, only the onchain step failed. You can try again.
                      </p>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={submitApproval}
                    disabled={selected.size === 0 || approveStatus === "submitting"}
                    style={{
                      ...primaryBtn,
                      alignSelf: "flex-start",
                      opacity: selected.size === 0 || approveStatus === "submitting" ? 0.4 : 1,
                      cursor: selected.size === 0 || approveStatus === "submitting" ? "default" : "pointer",
                    }}
                  >
                    {approveStatus === "submitting" ? "Committing..." : "Approve & Commit to Base"}
                  </button>
                </>
              )}

              {approveStatus === "done" && commitment && (
                <div
                  style={{
                    border: "1px solid #4ade80",
                    borderRadius: "12px",
                    padding: "20px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                  }}
                >
                  <p style={{ margin: 0, color: "#4ade80", fontWeight: 700, fontSize: "16px" }}>
                    ✓ Committed to Base Sepolia
                  </p>
                  <p style={{ margin: 0, fontSize: "13px", opacity: 0.7 }}>
                    Approved by {commitment.approved_by} · {commitment.claim_count} claim(s) ·
                    block {commitment.block_number}
                  </p>
                  <p style={{ margin: "8px 0 0 0", fontFamily: "monospace", fontSize: "13px" }}>
                    commitment_hash: {commitment.commitment_hash}
                  </p>
                  <p style={{ margin: 0, fontFamily: "monospace", fontSize: "13px" }}>
                    tx_hash: {commitment.tx_hash}
                  </p>
                  <a
                    href={commitment.basescan_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: "#4ade80", marginTop: "8px" }}
                  >
                    View on Basescan →
                  </a>
                </div>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
