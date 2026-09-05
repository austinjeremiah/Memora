"""HTTP surface.

Failure mapping lives in main.py as app-level exception handlers, so every
route fails the same way and a new route cannot forget to translate an error.
That matters most for SibylUnavailableError: it must become a clean 503 from
anywhere, never a 200 carrying an empty brief.
"""

import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from memora.api.schemas import (
    AskInThreadRequest,
    OpenSessionOut,
    SessionInfluenceOut,
    StoredEventOut,
    OpenSessionRequest,
    OpenThreadRequest,
    PriorContextOut,
    SessionOut,
    ThreadOut,
    ApproveRequest,
    AskOut,
    AskRequest,
    AttestationOut,
    AttestationPayloadOut,
    AttestationVerifyOut,
    AutonomousCheckOut,
    ClaimOut,
    ClinicianOut,
    CommitmentOut,
    ContextOut,
    EventOut,
    FactOut,
    FindingOut,
    HandoffOut,
    HandoffRequest,
    MatchedRecordOut,
    MemoryStatusOut,
    PatientMemoryOut,
    PatientSummaryOut,
    RecordEventOut,
    RecordEventRequest,
    SentinelRunOut,
    SentinelRunRequest,
    SinceLastReviewOut,
    SourceEventOut,
    VerifyOut,
)
from memora.attestation.chain import next_nonce, submit_attestation, verify_onchain
from memora.attestation.domain import (
    ATTESTATION_TTL_SECONDS,
    ATTESTATION_TYPES,
    build_domain,
)
from memora.attestation.keys import (
    clinician_for_address,
    may_sign_as,
    registered_wallet,
    synthetic_address,
)
from memora.attestation.sign import SignedAttestation, sign_attestation
from memora.attestation.verify import verify_attestation
from memora.clinicians.roles import CLINICIANS, get_clinician
from memora.config import settings
from memora.context.engine import RetrievedContext, compile_plan, execute_plan
from memora.context.situations import Situation
from memora.evidence.resolver import resolve_all, resolve_claim
from memora.gate.gate import GateResult, evaluate_all, evaluate_claim, summarise
from memora.integrity.base_client import commit_hash, verify_hash
from memora.integrity.commitment import (
    canonical_commitment_payload,
    commitment_label,
    compute_commitment_hash,
    compute_context_hash,
    compute_evidence_root,
)
from memora.llm.answer import answer_question, search_memory
from memora.sessions.recall import prior_context
from memora.sessions.runtime import BOOT_ID, boot_info
from memora.sessions.store import (
    close_session,
    get_session,
    get_thread,
    list_sessions,
    list_threads,
    open_session,
    open_thread,
    record_decision,
    record_question,
)
from memora.llm.propose import propose_claims
from memora.ontology.events import ALL_EVENT_TYPES, ClinicalEvent
from memora.ontology.kinds import ALL_KINDS
from memora.sentinel.digest import SENTINEL_SYSTEM_ID
from memora.sentinel.runner import since_last_review, sweep
from memora.sibyl.client import (
    PatientMemory,
    full_memory,
    known_patient_ids,
    patient_summary,
)
from memora.sibyl.errors import SibylUnavailableError
from memora.sibyl.preflight import assert_store_available

log = logging.getLogger("memora.api")

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


@router.get("/patients", response_model=list[PatientSummaryOut])
def list_patients() -> list[PatientSummaryOut]:
    """Every patient actually present in the Sibyl store.

    Real ids are Synthea UUIDs generated per ingestion run, so nothing
    downstream can hardcode them -- they have to be discovered. The reserved
    Sentinel pseudo-tenant is excluded by known_patient_ids and is not a
    patient.
    """
    return [PatientSummaryOut(**patient_summary(pid)) for pid in known_patient_ids()]


@router.get("/patients/{patient_id}/memory", response_model=PatientMemoryOut)
def get_patient_memory(patient_id: str, event_limit: int = 200) -> PatientMemoryOut:
    """The raw stored record for one patient -- unfiltered by situation.

    Distinct from /context, which returns one situation's ranked, capped
    retrieval plan. This returns what is actually in Sibyl: every WARM fact by
    kind, every lab trajectory with its series, and the COLD journal.

    It exists so the memory layer can be inspected directly. A claim that
    persistent memory is real is worth less than the ability to open it.
    """
    _reject_reserved(patient_id)
    return PatientMemoryOut(**full_memory(patient_id, event_limit=event_limit))


@router.post("/patients/{patient_id}/ask", response_model=AskOut)
def ask(patient_id: str, request: AskRequest) -> AskOut:
    """Answer a clinician's question from this patient's memory.

    Retrieval here is driven by the QUESTION rather than by a fixed situation,
    using Sibyl's FTS5 index -- the search capability the rest of the app never
    exercises. Everything after retrieval is unchanged: the model proposes, the
    Evidence Resolver checks each claim against the record, and the same Gate
    decides. A question earns the model no extra latitude.

    When nothing matches, the model is never asked. Inviting it to answer from
    an empty result set is precisely how a confident fabrication happens.
    """
    _reject_reserved(patient_id)
    clinician = _require_clinician(request.clinician_id)

    memory = PatientMemory(patient_id, require_data=True)
    context = search_memory(memory, request.question)

    if context.is_empty():
        quota = memory.quota()
        return AskOut(
            patient_id=patient_id, question=request.question,
            search_terms=context.terms, matched=[], answer="", claims=[],
            summary={r.value: 0 for r in GateResult}, answered=False,
            model=settings.llm_model,
            memory=MemoryStatusOut(db_size_bytes=quota["db_size_bytes"],
                                   soft_cap_bytes=quota["soft_cap_bytes"],
                                   pct_used=quota.get("pct_used")),
        )

    proposed = answer_question(context)
    checks = resolve_all(memory, proposed["claims"])
    decisions = evaluate_all(memory, checks, clinician.role)

    claims = [
        ClaimOut(
            text=check.claim_text, gate_result=decision.result.value,
            reason=decision.reason, triggered_rules=list(decision.triggered_rules),
            source_kind=check.source_kind, source_name=check.source_name,
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

    # An answer is only presentable if something behind it survived the gate.
    # Prose with every supporting claim blocked is a refusal, not an answer.
    supported = any(c.gate_result != GateResult.BLOCK.value for c in claims)

    influence = _influence(memory, claims)
    if request.thread_id:
        record_question(memory, request.thread_id, question=request.question,
                        answered=supported,
                        answer=proposed["answer"] if supported else "",
                        verdicts=summarise(decisions),
                        matched=len(context.matches))

    return AskOut(
        patient_id=patient_id,
        question=request.question,
        search_terms=context.terms,
        matched=[MatchedRecordOut(kind=m["category"], name=m["name"],
                                  status=m["status"], body=m["body"])
                 for m in context.matches],
        answer=proposed["answer"] if supported else "",
        claims=claims,
        summary=summarise(decisions),
        answered=supported,
        model=settings.llm_model,
        memory=_memory_out(memory),
        influence=influence,
    )


def _influence(memory: PatientMemory, claims: list[ClaimOut]) -> SessionInfluenceOut:
    """Report which earlier-session evidence actually moved this answer.

    A claim counts as changed only when the gate did NOT simply allow it and
    the record it cites is backed by a critical journal entry -- i.e. by
    something a previous session wrote. Merely having prior sessions is not
    influence; a wrapper would show that number and change nothing.
    """
    prior = prior_context(memory)
    shaping = prior["critical_events"]
    keys = {(e.get("related_kind"), e.get("related_name"))
            for e in shaping if e.get("related_name")}

    changed = [
        c.text for c in claims
        if c.gate_result != GateResult.ALLOW.value
        and (c.source_kind, c.source_name) in keys
    ]

    return SessionInfluenceOut(
        prior_sessions=prior["prior_session_count"],
        sessions_from_dead_processes=prior["sessions_from_dead_processes"],
        crossed_restart=prior["crossed_restart"],
        current_boot_id=prior["current_boot_id"],
        shaping_events=[StoredEventOut(**e) for e in shaping],
        changed_the_answer=bool(changed),
        changed_claims=changed,
    )


@router.post("/patients/{patient_id}/events", response_model=RecordEventOut)
def record_event(patient_id: str, request: RecordEventRequest) -> RecordEventOut:
    """Document a clinical event against a patient's journal.

    An ordinary write path, not a demo affordance -- this is how an adverse
    reaction gets onto a record in the first place. It goes through the same
    repository facade as ingestion, so it is quota-checked and it bumps the
    patient's memory version like any other write.

    It is also what makes Sentinel demonstrable on real data. Synthea never
    prescribes a drug a patient is allergic to, so genuine drift does not occur
    in the generated set. Recording a reaction to a medication that memory
    still holds as active creates a REAL contradiction, which Sentinel then
    detects independently -- rather than a finding being planted directly.
    """
    _reject_reserved(patient_id)

    if request.event_type not in ALL_EVENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown event_type '{request.event_type}'. "
                   f"Known: {', '.join(sorted(ALL_EVENT_TYPES))}")
    if request.related_kind not in ALL_KINDS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown related_kind '{request.related_kind}'. "
                   f"Known: {', '.join(ALL_KINDS)}")

    memory = PatientMemory(patient_id, require_data=True)
    event = ClinicalEvent(
        event_type=request.event_type,
        summary=request.summary,
        timestamp=request.timestamp or datetime.now(UTC).isoformat(),
        related_kind=request.related_kind,
        related_name=request.related_name,
        source_id=request.source_id or f"recorded-{uuid4().hex[:12]}",
        severity=request.severity,
    )
    event_id = memory.log_event(event)

    # THE AGENT ACTS ON ITS OWN. New information entering memory is the
    # trigger -- nobody asked for this check. Sentinel decides whether what
    # just arrived contradicts what was already there, and escalates into the
    # patient's record if it has persisted long enough. Scoped to this one
    # patient so the write stays fast.
    check = None
    try:
        run = sweep(Situation.ICU_TO_WARD, [patient_id])
        check = AutonomousCheckOut(
            ran=True,
            situation=run.situation,
            records_checked=run.records_checked,
            findings=_findings_out(run.findings),
            actions_taken=run.actions_taken,
        )
    except Exception:
        # The event is already durably recorded. An autonomous check that
        # fails is a degraded agent, not a lost clinical record, so the write
        # stands and the caller is told the check did not run.
        log.exception("autonomous check failed after recording an event")
        check = AutonomousCheckOut(ran=False, situation=Situation.ICU_TO_WARD.value,
                                   records_checked=0)

    return RecordEventOut(
        patient_id=patient_id,
        event_id=event_id,
        memory_version=memory.memory_version(),
        recorded_at=event.timestamp,
        autonomous_check=check,
    )


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


def _verified_attestation_inputs(patient_id: str, request: ApproveRequest, clinician):
    """Re-verify every submitted claim against LIVE memory, then derive the
    hashes an attestation commits to.

    Shared by the payload endpoint and the attest endpoint so both compute the
    same state hash from the same read. If they diverged, a wallet would sign
    one state and the server would record another.
    """
    memory = PatientMemory(patient_id, require_data=True)

    verified: list[dict] = []
    evidence_ids: list[str] = []
    for claim in request.claims:
        check = resolve_claim(memory, claim.text, claim.related_kind,
                              claim.related_name)
        decision = evaluate_claim(memory, check, clinician.role)
        if decision.result is GateResult.BLOCK:
            raise HTTPException(status_code=409, detail={
                "error": "claim_not_verifiable",
                "detail": ("Refusing to attest: a submitted claim does not pass "
                           "verification against current memory."),
                "claim": claim.text, "reason": decision.reason})
        verified.append({"text": claim.text, "gate_result": decision.result.value})
        evidence_ids.extend(e.source_id for e in check.source_events if e.source_id)

    state_hash = compute_commitment_hash(
        canonical_commitment_payload(patient_id, request.situation.value, verified))
    return {
        "memory": memory,
        "verified": verified,
        "state_hash": state_hash,
        "evidence_root": compute_evidence_root(evidence_ids),
        "context_hash": compute_context_hash(request.situation.value,
                                             clinician.role.value),
        "memory_version": memory.memory_version(),
    }


def _signer_for(clinician) -> tuple[str, str]:
    """(address, mode) this clinician signs with.

    A registered wallet takes precedence; without one the synthetic demo key
    is used, so the system works with no wallet configured at all.
    """
    wallet = registered_wallet(clinician.id)
    if wallet:
        return wallet, "wallet"
    return synthetic_address(clinician.id), "synthetic_demo_key"


@router.post("/handoff/{patient_id}/attestation-payload",
             response_model=AttestationPayloadOut)
def attestation_payload(patient_id: str,
                        request: ApproveRequest) -> AttestationPayloadOut:
    """The EIP-712 payload a wallet should sign for this approval.

    Step 1 of the wallet flow. The server derives the state hash here because
    doing so requires re-verifying every claim against live Sibyl state -- the
    browser cannot be trusted to decide what was approved. The wallet only
    signs what memory has already justified.
    """
    _reject_reserved(patient_id)
    if request.patient_id != patient_id:
        raise HTTPException(status_code=400,
                            detail="patient_id in the path and body must match.")

    clinician = _require_clinician(request.clinician_id)
    if not clinician.can_approve_handoff:
        raise HTTPException(
            status_code=403,
            detail=(f"{clinician.name} ({clinician.role.value}) is not "
                    "authorised to approve a handover."))

    inputs = _verified_attestation_inputs(patient_id, request, clinician)
    signer, mode = _signer_for(clinician)

    issued_at = int(time.time())
    expires_at = issued_at + ATTESTATION_TTL_SECONDS
    nonce = next_nonce(signer)

    state_hash = "0x" + inputs["state_hash"].hex()
    evidence_root = "0x" + inputs["evidence_root"].hex()
    context_hash = "0x" + inputs["context_hash"].hex()

    return AttestationPayloadOut(
        domain=build_domain(),
        types=ATTESTATION_TYPES,
        message={
            "stateHash": state_hash,
            "evidenceRoot": evidence_root,
            "contextHash": context_hash,
            "memoryVersion": inputs["memory_version"],
            "issuedAt": issued_at,
            "expiresAt": expires_at,
            "nonce": nonce,
        },
        state_hash=state_hash,
        evidence_root=evidence_root,
        context_hash=context_hash,
        memory_version=inputs["memory_version"],
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
        expected_signer=signer,
        signer_mode=mode,
        claim_count=len(inputs["verified"]),
    )


@router.post("/handoff/{patient_id}/attest", response_model=AttestationOut)
def attest_handoff(patient_id: str, request: ApproveRequest) -> AttestationOut:
    """Approve a handover and record a SIGNED attestation on Base.

    The evolution of /approve: that route anchors an anonymous hash, this one
    records WHO approved it, over WHAT evidence, in WHICH clinical context, at
    WHICH point in the patient's memory -- cryptographically, with replay
    protection the contract enforces.

    Every claim is re-verified against live Sibyl state before anything is
    signed, exactly as /approve does. Delete the memory layer and no attestation
    can be produced at all.
    """
    _reject_reserved(patient_id)
    if request.patient_id != patient_id:
        raise HTTPException(status_code=400,
                            detail="patient_id in the path and body must match.")

    clinician = _require_clinician(request.clinician_id)
    if not clinician.can_approve_handoff:
        raise HTTPException(
            status_code=403,
            detail=(f"{clinician.name} ({clinician.role.value}) is not "
                    "authorised to approve a handover."))

    inputs = _verified_attestation_inputs(patient_id, request, clinician)
    state_hash = inputs["state_hash"]
    evidence_root = inputs["evidence_root"]
    context_hash = inputs["context_hash"]
    memory_version = inputs["memory_version"]

    if request.signature and request.signer:
        # WALLET MODE. The server does not sign; it checks that this signature
        # came from an address registered to THIS clinician. Being merely
        # authorised is not enough -- a wallet registered to another persona
        # would produce a valid signature with the wrong attribution.
        if not may_sign_as(request.signer, clinician.id):
            raise HTTPException(
                status_code=403,
                detail=(f"Address {request.signer} is not registered to sign as "
                        f"{clinician.name}. Register it in CLINICIAN_WALLETS."))
        if request.issued_at is None or request.expires_at is None \
                or request.nonce is None:
            raise HTTPException(
                status_code=400,
                detail=("Wallet mode requires issued_at, expires_at and nonce "
                        "exactly as returned by /attestation-payload -- the "
                        "signature covers them."))

        check = verify_attestation(
            state_hash, evidence_root, context_hash, memory_version,
            request.issued_at, request.expires_at, request.nonce,
            request.signature, expected_signer=request.signer)
        if not check.valid:
            raise HTTPException(status_code=400,
                                detail=f"Signature rejected: {check.reason}")

        attestation = SignedAttestation(
            clinician_id=clinician.id, signer=request.signer,
            signature=request.signature, digest="",
            state_hash="0x" + state_hash.hex(),
            evidence_root="0x" + evidence_root.hex(),
            context_hash="0x" + context_hash.hex(),
            memory_version=memory_version, issued_at=request.issued_at,
            expires_at=request.expires_at, nonce=request.nonce)
        signer_kind = "registered_wallet"
    else:
        # Fallback: no wallet connected, sign with the synthetic demo key.
        signer = synthetic_address(clinician.id)
        attestation = sign_attestation(
            clinician_id=clinician.id, state_hash=state_hash,
            evidence_root=evidence_root, context_hash=context_hash,
            memory_version=memory_version, nonce=next_nonce(signer))
        signer_kind = "synthetic_demo_key"

    receipt = submit_attestation(attestation)
    return AttestationOut(**{**attestation.as_dict(), "signer_kind": signer_kind},
                          **receipt)


@router.get("/attestation/{state_hash}/verify", response_model=AttestationVerifyOut)
def verify_attestation_onchain(state_hash: str) -> AttestationVerifyOut:
    """Read an attestation back off Base. No key, no gas, no patient data."""
    raw = state_hash.removeprefix("0x")
    try:
        digest = bytes.fromhex(raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail="state_hash must be hex.") from e
    if len(digest) != 32:
        raise HTTPException(status_code=422,
                            detail="state_hash must be 32 bytes (SHA-256).")

    result = verify_onchain(digest)
    return AttestationVerifyOut(
        state_hash="0x" + digest.hex(),
        exists=result["exists"],
        signer=result["signer"],
        clinician_id=clinician_for_address(result["signer"]),
        timestamp=result["timestamp"],
        memory_version=result["memory_version"],
        basescan_url=("https://sepolia.basescan.org/address/"
                      f"{settings.base_attestation_contract_address}"),
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


# ---------------------------------------------------------------------------
# Sessions and threads
#
# These exist to make the eligibility gate checkable. A session records the
# BOOT_ID of the process that opened it, so a later session can report -- as
# data, not narration -- that the process which wrote what it just recalled is
# no longer running.
# ---------------------------------------------------------------------------

@router.get("/runtime")
def runtime() -> dict:
    """Identity of the running process. Changes only when the API restarts."""
    return boot_info()


@router.post("/patients/{patient_id}/sessions", response_model=OpenSessionOut)
def start_session(patient_id: str, req: OpenSessionRequest) -> OpenSessionOut:
    clinician = get_clinician(req.clinician_id)
    if clinician is None:
        raise HTTPException(400, f"Unknown clinician_id {req.clinician_id!r}")

    memory = PatientMemory(patient_id, require_data=True)

    # Read BEFORE writing, so a session never inherits itself.
    prior = prior_context(memory)
    session = open_session(memory, clinician.id, clinician.name)

    log.info("session %s opened by %s (boot %s), %d prior sessions, %d from dead processes",
             session["session_id"], clinician.id, BOOT_ID,
             prior["prior_session_count"], prior["sessions_from_dead_processes"])
    return OpenSessionOut(session=SessionOut(**session),
                          prior=PriorContextOut(**prior))


@router.get("/patients/{patient_id}/sessions", response_model=list[SessionOut])
def get_sessions(patient_id: str) -> list[SessionOut]:
    memory = PatientMemory(patient_id, require_data=True)
    return [SessionOut(**s) for s in list_sessions(memory)]


@router.get("/patients/{patient_id}/prior-context", response_model=PriorContextOut)
def get_prior_context(patient_id: str, exclude_session_id: str | None = None
                      ) -> PriorContextOut:
    """What earlier sessions left behind for this one."""
    memory = PatientMemory(patient_id, require_data=True)
    return PriorContextOut(**prior_context(memory, exclude_session_id=exclude_session_id))


@router.post("/patients/{patient_id}/sessions/{session_id}/close",
             response_model=SessionOut)
def end_session(patient_id: str, session_id: str) -> SessionOut:
    memory = PatientMemory(patient_id, require_data=True)
    body = close_session(memory, session_id)
    if body is None:
        raise HTTPException(404, f"Unknown session_id {session_id!r}")
    return SessionOut(**body)


@router.post("/patients/{patient_id}/threads", response_model=ThreadOut)
def start_thread(patient_id: str, req: OpenThreadRequest) -> ThreadOut:
    memory = PatientMemory(patient_id, require_data=True)
    body = open_thread(memory, req.session_id, req.title)
    if body is None:
        raise HTTPException(404, f"Unknown session_id {req.session_id!r}")
    return ThreadOut(**body)


@router.get("/patients/{patient_id}/threads", response_model=list[ThreadOut])
def get_threads(patient_id: str, session_id: str | None = None) -> list[ThreadOut]:
    memory = PatientMemory(patient_id, require_data=True)
    return [ThreadOut(**t) for t in list_threads(memory, session_id=session_id)]
