"""Evidence Resolver -- turns "evidence-linked" into a code-level guarantee.

Every claim a model proposes is checked against what is actually in Sibyl
before anything downstream may present it as verified.

Two properties this module exists to hold:

  1. The LLM never grades its own work. Nothing here calls a model. Support is
     decided by whether a record exists, full stop -- putting the model back in
     charge of judging its own output would make the whole gate decorative.

  2. An unsourced claim is not evidence. A proposal that arrives without a
     (kind, name) pointer is rejected on that basis alone, no matter how
     clinically plausible the prose reads. That is the single most important
     rule here: fluent unsourced text is exactly the failure mode this product
     exists to catch.

Model output is untrusted input. It arrives as arbitrary JSON and may be
malformed, mistyped, or cite identifiers the SDK refuses. Every such case
resolves to "unsupported, and here is why" rather than an exception.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from memora.ontology.events import ClinicalEvent
from memora.ontology.kinds import ALL_KINDS
from memora.sibyl.client import PatientMemory
from memora.sibyl.keys import is_safe_identifier


class RejectionReason(str, Enum):
    """Why a claim failed. Typed so the Gate and the API can branch on it and
    tests can assert the exact cause rather than matching prose."""

    NO_CITATION = "no_citation"
    MALFORMED = "malformed"
    UNKNOWN_KIND = "unknown_kind"
    INVALID_IDENTIFIER = "invalid_identifier"
    NOT_IN_MEMORY = "not_in_memory"


REJECTION_TEXT = {
    RejectionReason.NO_CITATION:
        "Proposal cited no source record -- an unsourced claim cannot be verified.",
    RejectionReason.MALFORMED:
        "Proposal was not a well-formed claim object.",
    RejectionReason.UNKNOWN_KIND:
        "Proposal cited a record kind MEMORA does not track.",
    RejectionReason.INVALID_IDENTIFIER:
        "Proposal cited an identifier the memory store refuses.",
    RejectionReason.NOT_IN_MEMORY:
        "No current fact and no recorded event support this claim.",
}


@dataclass(frozen=True)
class EvidenceEvent:
    """One journal entry cited as provenance."""

    source_id: str | None
    event_type: str
    timestamp: str
    summary: str
    severity: str | None = None


@dataclass(frozen=True)
class EvidenceCheck:
    """The verdict on one proposed claim, with its provenance attached."""

    claim_text: str
    supported: bool
    source_kind: str | None = None
    source_name: str | None = None
    fact_status: str | None = None
    fact_body: dict | None = None
    source_events: tuple[EvidenceEvent, ...] = field(default_factory=tuple)
    rejection: RejectionReason | None = None

    @property
    def reason(self) -> str | None:
        return REJECTION_TEXT[self.rejection] if self.rejection else None

    @property
    def has_current_fact(self) -> bool:
        return self.fact_status is not None or self.fact_body is not None


def _reject(claim_text: str, reason: RejectionReason,
            kind: str | None = None, name: str | None = None) -> EvidenceCheck:
    return EvidenceCheck(claim_text=claim_text, supported=False,
                         source_kind=kind, source_name=name, rejection=reason)


def resolve_claim(memory: PatientMemory, claim_text: str,
                  related_kind: str | None, related_name: str | None) -> EvidenceCheck:
    """Check one claim against Sibyl. Deterministic: no model in the loop."""
    if not isinstance(claim_text, str) or not claim_text.strip():
        return _reject("", RejectionReason.MALFORMED)

    if not related_kind or not related_name:
        return _reject(claim_text, RejectionReason.NO_CITATION)
    if not isinstance(related_kind, str) or not isinstance(related_name, str):
        return _reject(claim_text, RejectionReason.MALFORMED)

    if related_kind not in ALL_KINDS:
        return _reject(claim_text, RejectionReason.UNKNOWN_KIND, related_kind, related_name)

    # Sibyl validates identifiers on write but NOT on read, so an unsafe
    # citation would otherwise slip through and be reported as merely absent.
    # A model can emit anything; check it here rather than trusting the SDK to.
    if not is_safe_identifier(related_name) or not is_safe_identifier(related_kind):
        return _reject(claim_text, RejectionReason.INVALID_IDENTIFIER, related_kind, related_name)

    fact = memory.get_fact(related_kind, related_name)

    events = _matching_events(memory, related_kind, related_name)

    if fact is None and not events:
        return _reject(claim_text, RejectionReason.NOT_IN_MEMORY, related_kind, related_name)

    return EvidenceCheck(
        claim_text=claim_text,
        supported=True,
        source_kind=related_kind,
        source_name=related_name,
        fact_status=fact["status"] if fact else None,
        fact_body=fact["body"] if fact else None,
        source_events=events,
    )


def _matching_events(memory: PatientMemory, kind: str, name: str) -> tuple[EvidenceEvent, ...]:
    """Find journal entries that cite this record.

    Matched on the structured extra fields written at ingestion, never by
    substring-searching the rendered row. Substring matching would both
    over-match (a drug whose name contains another's) and under-match (any
    change to how a summary is phrased), and neither failure would be visible.
    """
    matches = []
    for record in memory.read_history():
        event = ClinicalEvent.from_record(record)
        if event.related_kind == kind and event.related_name == name:
            matches.append(EvidenceEvent(
                source_id=event.source_id,
                event_type=event.event_type,
                timestamp=event.timestamp,
                summary=event.summary,
                severity=event.severity,
            ))
    matches.sort(key=lambda e: e.timestamp)
    return tuple(matches)


def resolve_all(memory: PatientMemory, proposed_claims: list[Any]) -> list[EvidenceCheck]:
    """Resolve a batch of model-proposed claims. Order is preserved."""
    checks = []
    for claim in proposed_claims:
        if not isinstance(claim, dict):
            checks.append(_reject("", RejectionReason.MALFORMED))
            continue
        checks.append(resolve_claim(
            memory,
            claim.get("text"),
            claim.get("related_kind"),
            claim.get("related_name"),
        ))
    return checks
