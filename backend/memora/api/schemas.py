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


class RecordEventRequest(BaseModel):
    """A clinical event being documented now.

    This is an ordinary clinical operation, not a demo affordance: adverse
    reactions, discontinuations and results are recorded as they happen. It
    matters for Sentinel because new information is precisely what makes
    memory contradict itself -- a medication recorded as active becomes a
    contradiction the moment a reaction to it is documented.
    """

    event_type: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=500)
    related_kind: str = Field(min_length=1, max_length=64)
    related_name: str = Field(min_length=1, max_length=512)
    severity: str | None = None
    timestamp: str | None = None      # ISO 8601; defaults to now
    source_id: str | None = None


class AutonomousCheckOut(BaseModel):
    """What Sentinel did on its own after new information arrived.

    Nobody asked for this check. New information entering memory is the
    trigger, which is what makes it the agent acting rather than a feature
    being invoked.
    """

    ran: bool
    situation: str
    records_checked: int
    findings: list[FindingOut] = []
    actions_taken: list[dict] = []


class RecordEventOut(BaseModel):
    patient_id: str
    event_id: str
    memory_version: int
    recorded_at: str
    autonomous_check: AutonomousCheckOut | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    clinician_id: str = Field(min_length=1, max_length=64)
    # Optional so every existing caller and test keeps working unchanged. When
    # present, the question is recorded on the thread and the answer reports
    # what earlier sessions contributed to it.
    thread_id: str | None = None


class MatchedRecordOut(BaseModel):
    kind: str
    name: str
    status: str | None
    body: dict | list | None


class AskOut(BaseModel):
    """An answer to a clinician's question, and everything behind it.

    `answer` is what a clinician reads first, but it is not trusted on its own:
    `claims` are the individual assertions it rests on, each carrying the
    gate's verdict. An answer whose claims were all blocked is shown as a
    refusal, not as prose.
    """

    patient_id: str
    question: str
    search_terms: list[str]
    matched: list[MatchedRecordOut]
    answer: str
    claims: list[ClaimOut]
    summary: dict[str, int]
    answered: bool
    model: str
    memory: MemoryStatusOut
    influence: SessionInfluenceOut | None = None


# ---------------------------------------------------------------------------
# Sessions and threads
#
# The eligibility gate asks for recall "in a genuinely fresh session". These
# carry `boot_id` for exactly that reason: a session written by a process that
# no longer exists proves the recall crossed a restart, rather than asking a
# judge to take the demo's word for it.
# ---------------------------------------------------------------------------

class OpenSessionRequest(BaseModel):
    clinician_id: str


class OpenThreadRequest(BaseModel):
    session_id: str
    title: str | None = None


class AskInThreadRequest(BaseModel):
    question: str
    clinician_id: str
    thread_id: str | None = None


class ThreadQuestionOut(BaseModel):
    question: str
    asked_at: str
    answered: bool
    answer_preview: str
    verdicts: dict[str, int] = {}
    records_matched: int = 0
    boot_id: str | None = None
    thread_id: str | None = None
    session_id: str | None = None
    clinician_id: str | None = None


class ThreadOut(BaseModel):
    thread_id: str
    session_id: str
    patient_id: str
    clinician_id: str | None = None
    title: str | None = None
    opened_at: str
    boot_id: str | None = None
    questions: list[ThreadQuestionOut] = []


class SessionDecisionOut(BaseModel):
    kind: str
    detail: str
    at: str
    boot_id: str | None = None
    session_id: str | None = None
    clinician_id: str | None = None


class SessionOut(BaseModel):
    session_id: str
    clinician_id: str
    clinician_name: str | None = None
    patient_id: str
    started_at: str
    ended_at: str | None = None
    boot_id: str | None = None
    threads: list[str] = []
    questions_asked: int = 0
    decisions: list[SessionDecisionOut] = []


class PriorContextOut(BaseModel):
    """What a fresh session inherits. `crossed_restart` is the gate's evidence."""

    current_boot_id: str
    prior_session_count: int
    sessions_from_dead_processes: int
    crossed_restart: bool
    memory_version: int
    sessions: list[SessionOut] = []
    questions: list[ThreadQuestionOut] = []
    decisions: list[SessionDecisionOut] = []
    critical_events: list[StoredEventOut] = []


class SessionInfluenceOut(BaseModel):
    """How memory written before this session changed this answer.

    `changed_the_answer` is true when a claim was blocked or flagged by a rule
    that fired on evidence an earlier session recorded. That is the difference
    between recalling context and being changed by it -- the distinction the
    eligibility gate is built around.
    """

    prior_sessions: int
    sessions_from_dead_processes: int
    crossed_restart: bool
    current_boot_id: str
    shaping_events: list[StoredEventOut] = []
    changed_the_answer: bool = False
    changed_claims: list[str] = []


class OpenSessionOut(BaseModel):
    session: SessionOut
    prior: PriorContextOut
