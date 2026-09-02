"""The deterministic safety gate.

One auditable decision point, three checks, no model anywhere in it. Every
claim passes through evaluate_claim before anything may present it as verified.

  1. EVIDENCE   is this actually supported by a Sibyl record?
  2. AUTHORITY  is this clinician permitted to see this kind of record?
  3. POLICY     does a declared clinical rule require escalation?

Evidence and authority are hard stops: either failing yields BLOCK immediately,
because there is nothing a policy rule could add to a claim that is unsupported
or that this clinician may not see.

Policy is different: every rule is evaluated, not just the first to fire, and
the decision carries all of them. Stopping at the first match would hide that a
claim tripped three separate rules, which is precisely what a reviewing
clinician needs to know.

WHY THIS CANNOT ALLOW WITHOUT MEMORY
------------------------------------
ALLOW is reachable only when evidence.supported is True, and that is set only
by the Evidence Resolver after a real Sibyl read. There is no cached path, no
default-allow branch, and no try/except that turns a failure into a pass.
Remove the memory layer and PatientMemory raises before a check ever runs; give
the gate an unsupported claim and it returns BLOCK. The gate cannot be talked
into ALLOW by better prose.
"""

from dataclasses import dataclass, field
from enum import Enum

from memora.context.situations import ClinicianRole
from memora.evidence.resolver import EvidenceCheck
from memora.gate.authority import has_authority
from memora.gate.policy import POLICY_RULES, PolicyRule
from memora.sibyl.client import PatientMemory


class GateResult(str, Enum):
    ALLOW = "ALLOW"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCK = "BLOCK"


# Most severe first. Used to fold multiple triggered rules into one verdict.
_SEVERITY = {GateResult.BLOCK: 2, GateResult.NEEDS_REVIEW: 1, GateResult.ALLOW: 0}


@dataclass(frozen=True)
class GateDecision:
    result: GateResult
    reason: str
    evidence: EvidenceCheck
    triggered_rules: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_presentable(self) -> bool:
        """Whether this may be shown to a clinician as verified output at all.
        NEEDS_REVIEW is presentable but only as flagged-for-review, never as
        settled fact -- the API and any UI must render it differently."""
        return self.result is not GateResult.ALLOW


def evaluate_claim(memory: PatientMemory, evidence: EvidenceCheck,
                   role: ClinicianRole) -> GateDecision:
    """The single function every proposed claim passes through."""

    # 1. EVIDENCE -- hard stop.
    if not evidence.supported:
        return GateDecision(
            result=GateResult.BLOCK,
            reason=evidence.reason or "Claim is not supported by any memory record.",
            evidence=evidence,
        )

    # 2. AUTHORITY -- hard stop.
    if not has_authority(role, evidence.source_kind):
        # role may be an unrecognised value rather than a ClinicianRole; an
        # unknown role must block cleanly, not raise on attribute access.
        role_label = getattr(role, "value", role)
        return GateDecision(
            result=GateResult.BLOCK,
            reason=(f"Role '{role_label}' is not authorised to view "
                    f"'{evidence.source_kind}' records."),
            evidence=evidence,
        )

    # 3. POLICY -- evaluate every rule, carry them all.
    triggered: list[PolicyRule] = [
        rule for rule in POLICY_RULES if rule.triggers(evidence, memory)
    ]

    if not triggered:
        return GateDecision(
            result=GateResult.ALLOW,
            reason="Supported by memory, authorised for this role, no policy conflict.",
            evidence=evidence,
        )

    verdict = max(
        (GateResult(rule.escalates_to) for rule in triggered),
        key=lambda r: _SEVERITY[r],
    )
    return GateDecision(
        result=verdict,
        reason="; ".join(f"{rule.name}: {rule.description}" for rule in triggered),
        evidence=evidence,
        triggered_rules=tuple(rule.name for rule in triggered),
    )


def evaluate_all(memory: PatientMemory, evidence_checks: list[EvidenceCheck],
                 role: ClinicianRole) -> list[GateDecision]:
    return [evaluate_claim(memory, check, role) for check in evidence_checks]


def summarise(decisions: list[GateDecision]) -> dict[str, int]:
    counts = {result.value: 0 for result in GateResult}
    for decision in decisions:
        counts[decision.result.value] += 1
    return counts
