"""Request and response models for the HTTP surface.

Responses carry provenance, not just verdicts. A claim's gate result is close
to useless to a clinician without the record it was drawn from, so every
non-blocked claim ships its cited record, that record's status, and the events
backing it. This is what makes "evidence-linked" visible at the API boundary
rather than only true internally.
"""

from pydantic import BaseModel, Field

from memora.context.situations import ClinicianRole, Situation


class HandoffRequest(BaseModel):
    patient_id: str = Field(min_length=1, max_length=512)
    situation: Situation
    clinician_id: str = Field(min_length=1, max_length=64)


class ClinicianOut(BaseModel):
    id: str
    name: str
    role: ClinicianRole
    can_approve_handoff: bool


class SourceEventOut(BaseModel):
    source_id: str | None
    event_type: str
    timestamp: str
    summary: str
    severity: str | None


class ClaimOut(BaseModel):
    text: str
    gate_result: str
    reason: str
    triggered_rules: list[str] = []
    source_kind: str | None = None
    source_name: str | None = None
    fact_status: str | None = None
    source_events: list[SourceEventOut] = []


class FactOut(BaseModel):
    kind: str
    name: str
    status: str | None
    body: dict | list | None
    updated_at: str


class EventOut(BaseModel):
    event_type: str
    summary: str
    timestamp: str
    severity: str | None = None
    related_kind: str | None = None
    related_name: str | None = None


class MemoryStatusOut(BaseModel):
    db_size_bytes: int
    soft_cap_bytes: int | None
    pct_used: float | None


class ContextOut(BaseModel):
    """Raw situational recall, before any model is involved."""

    patient_id: str
    situation: str
    task: str
    clinician: ClinicianOut
    facts: list[FactOut]
    history: list[EventOut]
    memory: MemoryStatusOut


class HandoffOut(BaseModel):
    patient_id: str
    situation: str
    task: str
    clinician: ClinicianOut
    claims: list[ClaimOut]
    summary: dict[str, int]
    proposed_count: int
    model: str
    memory: MemoryStatusOut
