"""HTTP surface.

Failure mapping lives in main.py as app-level exception handlers, so every
route fails the same way and a new route cannot forget to translate an error.
That matters most for SibylUnavailableError: it must become a clean 503 from
anywhere, never a 200 carrying an empty brief.
"""

from fastapi import APIRouter, HTTPException

from memora.api.schemas import (
    ClaimOut,
    ClinicianOut,
    ContextOut,
    EventOut,
    FactOut,
    HandoffOut,
    HandoffRequest,
    MemoryStatusOut,
    SourceEventOut,
)
from memora.clinicians.roles import CLINICIANS, get_clinician
from memora.config import settings
from memora.context.engine import RetrievedContext, compile_plan, execute_plan
from memora.evidence.resolver import resolve_all
from memora.gate.gate import evaluate_all, summarise
from memora.llm.propose import propose_claims
from memora.sibyl.client import PatientMemory
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
