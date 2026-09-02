"""HTTP surface.

Failure mapping lives in main.py as app-level exception handlers, so every
route fails the same way and a new route cannot forget to translate an error.
That matters most for SibylUnavailableError: it must become a clean 503 from
anywhere, never a 200 carrying an empty brief.
"""

from fastapi import APIRouter, HTTPException

from memora.api.schemas import (
    ApproveRequest,
    ClaimOut,
    ClinicianOut,
    CommitmentOut,
    ContextOut,
    EventOut,
    FactOut,
    FindingOut,
    HandoffOut,
    HandoffRequest,
    MemoryStatusOut,
    SentinelRunOut,
    SentinelRunRequest,
    SinceLastReviewOut,
    SourceEventOut,
    VerifyOut,
)
from memora.clinicians.roles import CLINICIANS, get_clinician
from memora.config import settings
from memora.context.engine import RetrievedContext, compile_plan, execute_plan
from memora.evidence.resolver import resolve_all, resolve_claim
from memora.gate.gate import GateResult, evaluate_all, evaluate_claim, summarise
from memora.integrity.base_client import commit_hash, verify_hash
from memora.integrity.commitment import (
    canonical_commitment_payload,
    commitment_label,
    compute_commitment_hash,
)
from memora.llm.propose import propose_claims
from memora.sentinel.digest import SENTINEL_SYSTEM_ID
from memora.sentinel.runner import since_last_review, sweep
from memora.sibyl.client import PatientMemory, known_patient_ids
from memora.sibyl.errors import SibylUnavailableError
from memora.sibyl.preflight import assert_store_available

router = APIRouter()


def _clinician_out(clinician) -> ClinicianOut:
    return ClinicianOut(id=clinician.id, name=clinician.name, role=clinician.role,
                        can_approve_handoff=clinician.can_approve_handoff)


def _memory_out(memory: PatientMemory) -> MemoryStatusOut:
    quota = memory.quota()
    return MemoryStatusOut(db_size_bytes=quota["db_size_bytes"],
                           soft_cap_bytes=quota["soft_cap_bytes"],
                           pct_used=quota.get("pct_used"))


def _reject_reserved(patient_id: str) -> None:
    """Sentinel's pseudo-tenant is not a patient and must never be addressable
    as one. It holds the digest, not clinical data -- surfacing it through a
    patient route would leak an internal structure into the clinical surface.
    """
    if patient_id == SENTINEL_SYSTEM_ID:
        raise HTTPException(status_code=404, detail=f"No such patient: {patient_id}")


def _require_clinician(clinician_id: str):
    clinician = get_clinician(clinician_id)
    if clinician is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown clinician_id '{clinician_id}'. "
                   f"Known: {', '.join(CLINICIANS)}",
        )
    return clinician


def _facts_out(context: RetrievedContext) -> list[FactOut]:
    return [
        FactOut(kind=kind, name=row["name"], status=row["status"],
                body=row["body"], updated_at=row["updated_at"])
        for kind, rows in context.facts.items()
        for row in rows
    ]


@router.get("/health")
def health() -> dict:
    """Liveness only. Says nothing about whether memory is reachable."""
    return {"status": "ok", "service": "memora"}


@router.get("/readyz")
def readyz() -> dict:
    """Readiness. Reports honestly that MEMORA cannot serve without Sibyl."""
    try:
        assert_store_available(settings.sibyl_db_path)
    except SibylUnavailableError as e:
        raise HTTPException(status_code=503,
                            detail={"status": "not_ready", "sibyl": False,
                                    "error": str(e)}) from e
    return {"status": "ready", "sibyl": True, "db_path": str(settings.sibyl_db_path)}


@router.get("/clinicians", response_model=list[ClinicianOut])
def list_clinicians() -> list[ClinicianOut]:
    return [_clinician_out(c) for c in CLINICIANS.values()]


@router.get("/patients/{patient_id}/context", response_model=ContextOut)
def get_context(patient_id: str, situation: str, clinician_id: str) -> ContextOut:
    """Situational recall with no model involved.

    Exists so the memory layer can be inspected on its own -- a judge can see
    that the same patient yields different subsets per situation without an
    LLM anywhere in the path.
    """
    _reject_reserved(patient_id)
    clinician = _require_clinician(clinician_id)
    from memora.context.situations import Situation

    try:
        parsed = Situation(situation)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown situation '{situation}'. "
                   f"Known: {', '.join(s.value for s in Situation)}",
        ) from e

    context = execute_plan(compile_plan(patient_id, parsed, clinician.role))
    memory = PatientMemory(patient_id)

    return ContextOut(
        patient_id=patient_id,
        situation=parsed.value,
        task=context.plan.task,
        clinician=_clinician_out(clinician),
        facts=_facts_out(context),
        history=[EventOut(event_type=e.event_type, summary=e.summary,
                          timestamp=e.timestamp, severity=e.severity,
                          related_kind=e.related_kind, related_name=e.related_name)
                 for e in context.history],
        memory=_memory_out(memory),
    )


@router.post("/handoff", response_model=HandoffOut)
def handoff(request: HandoffRequest) -> HandoffOut:
    """The full pipeline: recall -> propose -> verify -> gate."""
    _reject_reserved(request.patient_id)
    clinician = _require_clinician(request.clinician_id)

    context = execute_plan(
        compile_plan(request.patient_id, request.situation, clinician.role)
    )
    proposed = propose_claims(context)

    memory = PatientMemory(request.patient_id)
    checks = resolve_all(memory, proposed)
    decisions = evaluate_all(memory, checks, clinician.role)

    claims = [
        ClaimOut(
            text=check.claim_text,
            gate_result=decision.result.value,
            reason=decision.reason,
            triggered_rules=list(decision.triggered_rules),
            source_kind=check.source_kind,
            source_name=check.source_name,
            fact_status=check.fact_status,
            source_events=[
                SourceEventOut(source_id=e.source_id, event_type=e.event_type,
                               timestamp=e.timestamp, summary=e.summary,
                               severity=e.severity)
                for e in check.source_events
            ],
        )
        for check, decision in zip(checks, decisions, strict=True)
    ]

    return HandoffOut(
        patient_id=request.patient_id,
        situation=request.situation.value,
        task=context.plan.task,
        clinician=_clinician_out(clinician),
        claims=claims,
        summary=summarise(decisions),
        proposed_count=len(proposed),
        model=settings.llm_model,
        memory=_memory_out(memory),
    )


@router.post("/handoff/{patient_id}/approve", response_model=CommitmentOut)
def approve_handoff(patient_id: str, request: ApproveRequest) -> CommitmentOut:
    """Anchor a clinician-approved handover on Base.

    Two things happen before anything is signed, and both matter:

    1. The clinician's role must carry approval authority. A surgeon reviewing
       a ward handover cannot approve it, and that comes from the same
       authority table the gate uses -- not a separate permission list that
       could drift out of step with it.

    2. Every submitted claim is RE-VERIFIED against Sibyl right now. The client
       submits what it was shown, and the server independently re-resolves and
       re-gates each claim against current memory. Trusting a client-supplied
       verdict would let a caller anchor whatever it liked; re-checking means
       the onchain commitment attests to a state the server confirmed against
       persistent memory at approval time. Delete the memory layer and this
       endpoint cannot produce a commitment at all.

    Only a hash reaches the chain. No claim text, no clinical detail.
    """
    if request.patient_id != patient_id:
        raise HTTPException(
            status_code=400,
            detail="patient_id in the path and body must match.",
        )

    clinician = _require_clinician(request.clinician_id)
    if not clinician.can_approve_handoff:
        raise HTTPException(
            status_code=403,
            detail=(f"{clinician.name} ({clinician.role.value}) is not "
                    "authorised to approve a handover."),
        )

    memory = PatientMemory(patient_id, require_data=True)

    verified: list[dict] = []
    for claim in request.claims:
        check = resolve_claim(memory, claim.text, claim.related_kind,
                              claim.related_name)
        decision = evaluate_claim(memory, check, clinician.role)
        if decision.result is GateResult.BLOCK:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "claim_not_verifiable",
                    "detail": ("Refusing to commit: a submitted claim does not "
                               "pass verification against current memory."),
                    "claim": claim.text,
                    "reason": decision.reason,
                },
            )
        verified.append({"text": claim.text, "gate_result": decision.result.value})

    payload = canonical_commitment_payload(patient_id, request.situation.value,
                                           verified)
    digest = compute_commitment_hash(payload)
    label = commitment_label(patient_id, request.situation.value)

    receipt = commit_hash(digest, label)

    return CommitmentOut(
        patient_id=patient_id,
        situation=request.situation.value,
        approved_by=clinician.name,
        claim_count=len(verified),
        commitment_hash="0x" + digest.hex(),
        label=label,
        **receipt,
    )


@router.get("/commitment/{commitment_hash}/verify", response_model=VerifyOut)
def verify_commitment(commitment_hash: str) -> VerifyOut:
    """Read a commitment back off Base. No key, no gas, no patient data."""
    raw = commitment_hash.removeprefix("0x")
    try:
        digest = bytes.fromhex(raw)
    except ValueError as e:
        raise HTTPException(status_code=422,
                            detail="commitment_hash must be hex.") from e
    if len(digest) != 32:
        raise HTTPException(status_code=422,
                            detail="commitment_hash must be 32 bytes (SHA-256).")

    result = verify_hash(digest)
    return VerifyOut(
        commitment_hash="0x" + digest.hex(),
        exists=result["exists"],
        timestamp=result["timestamp"],
        committer=result["committer"],
        basescan_url=("https://sepolia.basescan.org/address/"
                      f"{settings.base_commitment_contract_address}"),
    )


# ---------------------------------------------------------------------------
# Sentinel -- the proactive path. No model is reachable from any of it.
# ---------------------------------------------------------------------------

def _findings_out(findings) -> list[FindingOut]:
    return [FindingOut(**f.as_dict()) if not isinstance(f, dict) else FindingOut(**f)
            for f in findings]


@router.post("/sentinel/run", response_model=SentinelRunOut)
def sentinel_run(request: SentinelRunRequest) -> SentinelRunOut:
    """Sweep patients for memory drift and reconcile against the digest.

    No LLM is called anywhere in this path -- findings are built directly from
    persisted records and judged by the same Gate the reactive path uses.
    """
    patient_ids = request.patient_ids
    if patient_ids is None:
        patient_ids = known_patient_ids()
    patient_ids = [p for p in patient_ids if p != SENTINEL_SYSTEM_ID]

    run = sweep(request.situation, patient_ids,
                escalation_threshold=request.escalation_threshold)
    return SentinelRunOut(
        situation=run.situation,
        run_at=run.run_at,
        patients_scanned=run.patients_scanned,
        records_checked=run.records_checked,
        summary=run.by_status(),
        findings=_findings_out(run.findings),
        announceable=_findings_out(run.announceable()),
        digest_commitment=run.digest_commitment,
    )


@router.get("/sentinel/since-last-review", response_model=SinceLastReviewOut)
def sentinel_since_last_review(patient_id: str, situation: str) -> SinceLastReviewOut:
    """What changed since this clinician last looked. Pure read, no detection."""
    _reject_reserved(patient_id)
    from memora.context.situations import Situation

    try:
        parsed = Situation(situation)
    except ValueError as e:
        raise HTTPException(status_code=422,
                            detail=f"Unknown situation '{situation}'.") from e

    buckets = since_last_review(parsed, patient_id)
    return SinceLastReviewOut(
        patient_id=patient_id,
        situation=parsed.value,
        new=_findings_out(buckets["new"]),
        persisting=_findings_out(buckets["persisting"]),
        escalated=_findings_out(buckets["escalated"]),
    )
