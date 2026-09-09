"""Sentinel sweeps -- the periodic reconciliation pass.

Two detection paths, deliberately split by what each one needs:

  DELTA is event-triggered. The ingestion pipeline already knows old-value vs
  new-value at the moment a fact changes, so it hands that straight to
  evaluate_delta rather than having Sentinel re-read Sibyl to re-derive it.
  Duplicating that logic would create a second place "what changed" could drift
  out of step with the first.

  DRIFT is swept. It needs no previous value -- it compares a record against
  its own journal -- so it can run over everything, on a schedule, and catch
  contradictions that were already sitting in memory before Sentinel existed.

Both converge on the same digest and the same state machine, so a finding
behaves identically regardless of which path found it.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from memora.context.situations import SITUATION_FOCUS, Situation
from memora.gate.gate import GateDecision, GateResult
from memora.sentinel.actions import escalate
from memora.sentinel.digest import (
    Finding,
    load_digest,
    merge_finding,
    save_digest,
)
from memora.sentinel.drift import check_drift
from memora.sentinel.state_machine import (
    FindingStatus,
    is_announceable,
    transition,
)
from memora.sibyl.client import PatientMemory

log = logging.getLogger("memora.sentinel")


@dataclass
class SentinelRun:
    situation: str
    run_at: str
    patients_scanned: int = 0
    records_checked: int = 0
    findings: list[Finding] = field(default_factory=list)
    digest_commitment: str | None = None
    # What the agent DID this run, not merely what it noticed.
    actions_taken: list[dict] = field(default_factory=list)

    def announceable(self) -> list[Finding]:
        return [f for f in self.findings
                if is_announceable(FindingStatus(f.status))]

    def by_status(self) -> dict[str, int]:
        counts = {s.value: 0 for s in FindingStatus}
        for finding in self.findings:
            counts[finding.status] += 1
        return counts

    def as_dict(self) -> dict:
        return {
            "situation": self.situation,
            "run_at": self.run_at,
            "patients_scanned": self.patients_scanned,
            "records_checked": self.records_checked,
            "summary": self.by_status(),
            "findings": [f.as_dict() for f in self.findings],
            "actions_taken": self.actions_taken,
            "digest_commitment": self.digest_commitment,
        }


def _finding_from_decision(patient_id: str, kind: str, name: str,
                           decision: GateDecision, detector: str,
                           now: str) -> Finding:
    evidence_event = None
    if decision.evidence.source_events:
        first = decision.evidence.source_events[0]
        evidence_event = f"{first.event_type}@{first.timestamp[:10]}"
    return Finding(
        patient_id=patient_id,
        kind=kind,
        name=name,
        status=FindingStatus.NEW.value,   # replaced by the state machine below
        gate_result=decision.result.value,
        reason=decision.reason,
            first_seen_at=now,
        last_seen_at=now,
        triggered_rules=list(decision.triggered_rules),
        evidence_event=evidence_event,
        detector=detector,
    )


def sweep(situation: Situation, patient_ids: list[str],
          escalation_threshold: int = 3) -> SentinelRun:
    """Run drift detection across patients and reconcile against the digest."""
    now = datetime.now(UTC).isoformat()
    run = SentinelRun(situation=situation.value, run_at=now)
    previous_digest = load_digest(situation.value)
    kinds = SITUATION_FOCUS[situation].kinds

    # These INFO lines are the agent narrating itself. The sweep is otherwise
    # invisible -- it writes to the patient record without anyone asking, which
    # is exactly the part worth being able to watch happen.
    log.info("[sentinel] sweep start  situation=%s  patients=%d  kinds=%s",
             situation.value, len(patient_ids), ",".join(kinds))
    log.info("[sentinel] recalled digest from previous runs: %d tracked finding(s)",
             len(previous_digest))

    current: dict[str, Finding] = {}

    for patient_id in patient_ids:
        memory = PatientMemory(patient_id)
        run.patients_scanned += 1
        before = run.records_checked

        for kind in kinds:
            for row in memory.list_facts(kind):
                run.records_checked += 1
                decision = check_drift(memory, kind, row["name"], row["status"])
                if decision is None:
                    continue
                log.info("[sentinel]   CONTRADICTION  %s/%s  -- %s",
                         kind, row["name"][:44], decision.reason[:80])
                finding = _finding_from_decision(
                    patient_id, kind, row["name"], decision, "drift", now)
                current[finding.key] = finding

        log.info("[sentinel]   read %s: %d records from persistent memory",
                 patient_id[:8], run.records_checked - before)

    # Anything previously flagged that no longer trips the check has resolved.
    for key, prior in previous_digest.items():
        if key in current or prior.get("detector") != "drift":
            continue
        resolved = Finding(**{**prior, "last_seen_at": now,
                              "gate_result": GateResult.ALLOW.value,
                              "reason": "Condition no longer detected."})
        current[key] = resolved

    findings: list[Finding] = []
    updated_digest: dict[str, dict] = {}

    for key, finding in current.items():
        prior = previous_digest.get(key)
        runs_seen = int(prior.get("runs_seen", 0)) + 1 if prior else 1
        status = transition(
            previous_status=prior.get("status") if prior else None,
            gate_result=finding.gate_result,
            runs_since_first_seen=runs_seen,
            escalation_threshold=escalation_threshold,
        )
        if status is None:
            continue  # clean result on something never flagged -- not a finding
        merged = merge_finding(prior, finding, status)
        findings.append(merged)
        log.info("[sentinel]   %-11s %s/%s  (seen %dx across runs)",
                 status.value, merged.kind, merged.name[:40], merged.runs_seen)

        # THE ACTION. Only reachable because the digest remembered how many
        # times this was already seen -- without that persisted count there is
        # no escalation threshold to cross.
        if status is FindingStatus.ESCALATED:
            log.info("[sentinel]   ACTING UNPROMPTED: threshold of %d runs crossed, "
                     "writing an escalation into %s's record",
                     escalation_threshold, merged.patient_id[:8])
            event_id = escalate(PatientMemory(merged.patient_id), merged)
            if event_id:
                run.actions_taken.append({
                    "action": "escalated_to_patient_record",
                    "patient_id": merged.patient_id,
                    "kind": merged.kind,
                    "name": merged.name,
                    "event_id": event_id,
                    "runs_seen": merged.runs_seen,
                })
        # A resolved finding is reported this run, then dropped from the digest
        # so it does not resurface forever as stale state.
        if status is not FindingStatus.RESOLVED:
            updated_digest[key] = merged.as_dict()

    run.findings = sorted(findings, key=lambda f: (f.patient_id, f.kind, f.name))
    save_digest(situation.value, updated_digest, run_at=now)
    log.info("[sentinel] digest saved to memory: %d finding(s) carried to the next run",
             len(updated_digest))
    log.info("[sentinel] sweep done  checked=%d  findings=%d  actions=%d  %s",
             run.records_checked, len(run.findings), len(run.actions_taken),
             run.by_status())
    return run


def since_last_review(situation: Situation, patient_id: str) -> dict:
    """Pure read over the stored digest -- no detection, no writes."""
    stored = load_digest(situation.value)
    buckets: dict[str, list[dict]] = {"new": [], "persisting": [], "escalated": []}
    for finding in stored.values():
        if finding.get("patient_id") != patient_id:
            continue
        bucket = finding.get("status", "").lower()
        if bucket in buckets:
            buckets[bucket].append(finding)
    return buckets
