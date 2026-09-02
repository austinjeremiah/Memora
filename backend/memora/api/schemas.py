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


class ApproveClaimIn(BaseModel):
    """A claim the clinician is approving, as it was shown to them."""

    text: str = Field(min_length=1)
    related_kind: str | None = None
    related_name: str | None = None


class ApproveRequest(BaseModel):
    patient_id: str = Field(min_length=1, max_length=512)
    situation: Situation
    clinician_id: str = Field(min_length=1, max_length=64)
    claims: list[ApproveClaimIn] = Field(min_length=1)


class CommitmentOut(BaseModel):
    patient_id: str
    situation: str
    approved_by: str
    claim_count: int
    commitment_hash: str
    label: str
    tx_hash: str
    block_number: int
    gas_used: int
    committer: str
    basescan_url: str


class VerifyOut(BaseModel):
    commitment_hash: str
    exists: bool
    timestamp: int
    committer: str
    basescan_url: str


class SentinelRunRequest(BaseModel):
    situation: Situation
    patient_ids: list[str] | None = None   # None = every ingested patient
    escalation_threshold: int = Field(default=3, ge=1, le=50)


class FindingOut(BaseModel):
    patient_id: str
    kind: str
    name: str
    status: str
    gate_result: str
    reason: str
    detector: str
    first_seen_at: str
    last_seen_at: str
    runs_seen: int
    triggered_rules: list[str] = []
    evidence_event: str | None = None


class SentinelRunOut(BaseModel):
    situation: str
    run_at: str
    patients_scanned: int
    records_checked: int
    summary: dict[str, int]
    findings: list[FindingOut]
    announceable: list[FindingOut]
    digest_commitment: str | None = None


class SinceLastReviewOut(BaseModel):
    patient_id: str
    situation: str
    new: list[FindingOut] = []
    persisting: list[FindingOut] = []
    escalated: list[FindingOut] = []
