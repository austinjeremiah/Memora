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

    # WALLET MODE (optional). When both are supplied the server does NOT sign:
    # it verifies this signature came from an address registered to this
    # clinician. Omit both and the server falls back to the clinician's
    # synthetic demo key, so the flow still works with no wallet connected.
    signature: str | None = None
    signer: str | None = None
    issued_at: int | None = None   # must match what the wallet actually signed
    expires_at: int | None = None
    nonce: int | None = None


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


class AttestationOut(BaseModel):
    """A clinician-signed attestation, recorded on Base.

    `signer` is a SYNTHETIC DEMO KEY held server-side. It is not a real
    clinician identity and not an authentication mechanism -- `signer_kind`
    says so in the response itself, not only in the docs.
    """

    clinician_id: str
    signer: str
    signer_kind: str = "synthetic_demo_key"   # or "registered_wallet"
    signature: str
    digest: str
    state_hash: str
    evidence_root: str
    context_hash: str
    memory_version: int
    issued_at: int
    expires_at: int
    nonce: int
    tx_hash: str
    block_number: int
    gas_used: int
    relayer: str
    basescan_url: str


class AttestationVerifyOut(BaseModel):
    state_hash: str
    exists: bool
    signer: str
    clinician_id: str | None = None
    timestamp: int
    memory_version: int
    basescan_url: str


class PatientSummaryOut(BaseModel):
    """Enough to choose a patient from a list.

    Real patient ids are Synthea UUIDs generated per ingestion run, so they
    cannot be hardcoded anywhere -- they have to be discovered from the store.
    """

    patient_id: str
    fact_count: int
    event_count: int
    memory_version: int
    kinds: dict[str, int]
    has_drug_allergy: bool
    last_updated: str | None = None


class StoredFactOut(BaseModel):
    name: str
    status: str | None
    body: dict | list | None
    created_at: str
    updated_at: str


class TrendOut(BaseModel):
    name: str
    test: str | None
    loinc: str | None
    unit: str | None
    direction: str | None
    delta: float | None
    readings: int | None
    latest_value: float | str | None
    latest_at: str | None
    series: list[dict]


class StoredEventOut(BaseModel):
    timestamp: str
    event_type: str
    summary: str
    severity: str | None = None
    related_kind: str | None = None
    related_name: str | None = None
    source_id: str | None = None


class PatientMemoryOut(BaseModel):
    """The raw record, unfiltered.

    Distinct from ContextOut, which is one situation's ranked and capped
    retrieval. This is what is actually stored.
    """

    patient_id: str
    memory_version: int
    fact_count: int
    event_count: int
    facts: dict[str, list[StoredFactOut]]
    trends: list[TrendOut]
    events: list[StoredEventOut]
    active_situation: dict | None = None
    memory: MemoryStatusOut


class AttestationPayloadOut(BaseModel):
    """The exact EIP-712 payload a wallet should sign.

    The server computes this because producing it requires re-verifying every
    claim against live Sibyl state -- a browser cannot be trusted to decide
    what the approved state hash is. The wallet's job is only to sign what
    memory has already justified.
    """

    domain: dict
    types: dict
    primary_type: str = "ClinicalAttestation"
    message: dict
    state_hash: str
    evidence_root: str
    context_hash: str
    memory_version: int
    issued_at: int
    expires_at: int
    nonce: int
    expected_signer: str | None = None
    signer_mode: str            # "wallet" | "synthetic_demo_key"
    claim_count: int
