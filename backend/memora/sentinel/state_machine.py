"""Finding lifecycle -- what stops Sentinel becoming noise.

A safety system that re-announces the same finding on every run trains
clinicians to ignore it. So a finding is announced once as NEW, then tracked as
PERSISTING until it either resolves or has persisted long enough to warrant
escalation. The transition is a pure function: same inputs, same result, every
time -- the same determinism discipline as the Context Engine's compile_plan.
"""

from enum import Enum


class FindingStatus(str, Enum):
    NEW = "NEW"                  # first time this finding has been seen
    PERSISTING = "PERSISTING"    # seen before, still unresolved, not yet escalated
    RESOLVED = "RESOLVED"        # the underlying condition no longer holds
    ESCALATED = "ESCALATED"      # unresolved for too long


DEFAULT_ESCALATION_THRESHOLD = 3


def transition(previous_status: str | None, gate_result: str,
               runs_since_first_seen: int,
               escalation_threshold: int = DEFAULT_ESCALATION_THRESHOLD,
               ) -> FindingStatus | None:
    """Decide a finding's new status.

    Returns None when there is nothing to report -- a clean gate result on
    something never flagged before is simply not a finding, and returning a
    status for it would put non-events in the digest.

    The return type is deliberately `FindingStatus | None`, not `FindingStatus`.
    The no-prior-finding-and-clean branch genuinely returns None, and annotating
    otherwise would be a lie a caller could act on.
    """
    resolved_now = gate_result == "ALLOW"

    if resolved_now:
        # Only meaningful if something was previously flagged. A clean result
        # on a never-flagged record is a non-event.
        if previous_status is None or previous_status == FindingStatus.RESOLVED:
            return None
        return FindingStatus.RESOLVED

    if previous_status is None:
        return FindingStatus.NEW

    # A resolved finding that recurs is genuinely new information, not a
    # continuation -- the condition came back, and that deserves announcing.
    if previous_status == FindingStatus.RESOLVED:
        return FindingStatus.NEW

    if previous_status == FindingStatus.ESCALATED:
        return FindingStatus.ESCALATED  # stays escalated until it resolves

    if runs_since_first_seen >= escalation_threshold:
        return FindingStatus.ESCALATED

    return FindingStatus.PERSISTING


def is_announceable(status: FindingStatus | None) -> bool:
    """Whether a status warrants surfacing to a clinician now.

    PERSISTING deliberately does not: it is visible in the digest and in the
    since-last-review view, but it does not re-alert. That distinction is the
    entire point of this module.
    """
    return status in (FindingStatus.NEW, FindingStatus.ESCALATED,
                      FindingStatus.RESOLVED)
