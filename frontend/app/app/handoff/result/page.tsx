"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { approveHandoff, requestHandoff } from "@/lib/api/client";
import { useAppStatus } from "@/lib/api/AppStatusContext";
import {
  ApproveClaimIn, ClaimOut, CommitmentOut, HandoffOut, MemoraApiError, Situation,
} from "@/lib/api/types";
import ClaimCard, { GateSummary } from "@/components/app/ClaimCard";
import AttestPanel from "@/components/app/AttestPanel";
import {
  Badge, Button, Card, EmptyState, Mono, Notice, Section, SkeletonList, StatTile,
} from "@/components/app/ui";

export default function HandoffResultPage() {
  return (
    <Suspense fallback={<SkeletonList rows={4} />}>
      <HandoffResultInner />
    </Suspense>
  );
}

function HandoffResultInner() {
  const params = useSearchParams();
  const { reportMemory } = useAppStatus();

  const patientId = params.get("patientId") ?? "";
  const situation = (params.get("situation") ?? "") as Situation | "";
  const clinicianId = params.get("clinicianId") ?? "";

  const [handoff, setHandoff] = useState<HandoffOut | null>(null);
  const [error, setError] = useState<MemoraApiError | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const [approving, setApproving] = useState(false);
  const [approveError, setApproveError] = useState<MemoraApiError | null>(null);
  const [commitment, setCommitment] = useState<CommitmentOut | null>(null);

  const fired = useRef(false);
  useEffect(() => {
    if (fired.current || !patientId || !situation || !clinicianId) return;
    fired.current = true;
    requestHandoff({ patient_id: patientId, situation, clinician_id: clinicianId })
      .then((res) => {
        setHandoff(res);
        reportMemory(res.memory);
        // Pre-select everything the gate allowed outright. NEEDS_REVIEW is
        // left unchecked on purpose -- a flagged claim should require a
        // deliberate click, not arrive pre-approved.
        setSelected(new Set(res.claims.filter((c) => c.gate_result === "ALLOW").map((c) => c.text)));
      })
      .catch((e) => setError(e as MemoraApiError));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId, situation, clinicianId]);

  if (!patientId || !situation || !clinicianId) {
    return (
      <EmptyState title="Nothing to run">
        <Link href="/app/handoff/new" style={{ color: "var(--accent-text)" }}>
          Start a handoff
        </Link>{" "}
        by choosing a patient, situation and clinician.
      </EmptyState>
    );
  }

  const toggle = (claim: ClaimOut) => setSelected((prev) => {
    const next = new Set(prev);
    next.has(claim.text) ? next.delete(claim.text) : next.add(claim.text);
    return next;
  });

  const approve = () => {
    if (!handoff) return;
    setApproving(true);
    setApproveError(null);
    const claims: ApproveClaimIn[] = handoff.claims
      .filter((c) => selected.has(c.text))
      .map((c) => ({ text: c.text, related_kind: c.source_kind, related_name: c.source_name }));

    approveHandoff(patientId, {
      patient_id: patientId, situation, clinician_id: clinicianId, claims,
    })
      .then(setCommitment)
      .catch((e) => setApproveError(e as MemoraApiError))
      .finally(() => setApproving(false));
  };

  const presentable = handoff?.claims.filter((c) => c.gate_result !== "BLOCK") ?? [];
  const blocked = handoff?.claims.filter((c) => c.gate_result === "BLOCK") ?? [];

  return (
    <div className="stack stack--loose">
      <div className="stack stack--tight">
        <Link href="/app/handoff/new" className="dim" style={{ textDecoration: "none" }}>
          ← New handoff
        </Link>
        <h1 className="page-title">Handover brief</h1>
        <div className="row" style={{ gap: 10 }}>
          <Mono truncate={20}>{patientId}</Mono>
          <Badge>{situation.replace(/_/g, " ")}</Badge>
          {handoff && <Badge tone="accent">{handoff.clinician.name}</Badge>}
        </div>
      </div>

      {error && (
        <Notice tone="error"
                title={error.code === "sibyl_unavailable"
                  ? "MEMORA cannot reach its memory layer"
                  : error.code === "llm_unavailable"
                    ? "The model provider is unreachable"
                    : "Could not produce this brief"}>
          {error.detail}
          {error.code === "sibyl_unavailable" && (
            <p style={{ marginBottom: 0, marginTop: 8 }}>
              It refuses rather than answering from nothing. That refusal is the
              intended behaviour.
            </p>
          )}
        </Notice>
      )}

      {!handoff && !error && (
        <div className="stack">
          <p className="subtle" style={{ margin: 0 }}>
            Recalling memory, asking the model, checking every claim against the record…
          </p>
          <SkeletonList rows={4} />
        </div>
      )}

      {handoff && (
        <>
          <div className="grid grid--3">
            <StatTile icon="database" label="Proposed" value={handoff.proposed_count}
                      hint={handoff.model} />
            <StatTile icon="shield" tone="amber" label="Survived the gate"
                      value={`${presentable.length}/${handoff.claims.length}`}
                      hint="the rest cited nothing that exists" />
            <StatTile icon="user" label="Task" value={handoff.task.replace(/_/g, " ")}
                      hint={`role: ${handoff.clinician.role.replace(/_/g, " ")}`} />
          </div>

          <Section title="Verdicts" action={<GateSummary claims={handoff.claims} />}>
            <div className="stack">
              {presentable.map((c) => (
                <ClaimCard key={c.text} claim={c} selectable
                           selected={selected.has(c.text)} onToggle={() => toggle(c)} />
              ))}
            </div>
          </Section>

          {blocked.length > 0 && (
            <Section title={`Refused — ${blocked.length}`}>
              <p className="dim" style={{ margin: 0 }}>
                The model proposed these. Memory could not support them, so they
                never reach the clinician as verified output.
              </p>
              <div className="stack">
                {blocked.map((c) => <ClaimCard key={c.text} claim={c} />)}
              </div>
            </Section>
          )}

          {selected.size > 0 && !commitment && (
            <AttestPanel
              patientId={patientId}
              situation={situation}
              clinicianId={clinicianId}
              claims={handoff.claims
                .filter((c) => selected.has(c.text))
                .map((c) => ({ text: c.text, related_kind: c.source_kind,
                               related_name: c.source_name }))}
            />
          )}

          {commitment ? (
            <Section title="Anchored on Base">
              <Card>
                <div className="stack stack--tight">
                  <span>
                    Approved by <strong>{commitment.approved_by}</strong> ·{" "}
                    {commitment.claim_count} claims
                  </span>
                  <span className="dim">
                    Only a SHA-256 digest went onchain. No clinical content.
                  </span>
                  <Mono>{commitment.commitment_hash}</Mono>
                  <div className="row">
                    <Button href={commitment.basescan_url} variant="primary">
                      View on Basescan
                    </Button>
                    <span className="dim">block {commitment.block_number}</span>
                  </div>
                </div>
              </Card>
            </Section>
          ) : (
            <Section title="Approve — anonymous hash (v1 mechanism)">
              <Card>
                <div className="stack">
                  {approveError && (
                    <Notice tone="error" title="Refused">
                      {approveError.detail}
                      {approveError.code === "claim_not_verifiable" && (
                        <p style={{ marginBottom: 0, marginTop: 8 }}>
                          Every claim is re-checked against live memory at approval
                          time — a stale one cannot be signed.
                        </p>
                      )}
                    </Notice>
                  )}
                  <div className="row row--between">
                    <span className="subtle">
                      {selected.size} of {presentable.length} claims selected
                      {!handoff.clinician.can_approve_handoff &&
                        ` · ${handoff.clinician.name} cannot approve`}
                    </span>
                    <Button variant="primary" onClick={approve}
                            disabled={approving || selected.size === 0 ||
                                      !handoff.clinician.can_approve_handoff}>
                      {approving ? "Verifying and anchoring…" : "Anchor hash only"}
                    </Button>
                  </div>
                </div>
              </Card>
            </Section>
          )}
        </>
      )}
    </div>
  );
}
