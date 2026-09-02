"""Finding lifecycle. Pure function -- no store, no network, no mocks needed."""

import pytest

from memora.sentinel.state_machine import (
    FindingStatus,
    is_announceable,
    transition,
)


def test_first_occurrence_is_new():
    assert transition(None, "BLOCK", 1) is FindingStatus.NEW


def test_repeated_finding_is_persisting_not_new():
    """The anti-alert-fatigue guarantee: a finding is announced once."""
    assert transition(FindingStatus.NEW, "BLOCK", 2) is FindingStatus.PERSISTING


def test_crossing_the_threshold_escalates():
    assert transition(FindingStatus.PERSISTING, "BLOCK", 3,
                      escalation_threshold=3) is FindingStatus.ESCALATED


def test_escalated_stays_escalated_until_resolved():
    assert transition(FindingStatus.ESCALATED, "BLOCK", 9) is FindingStatus.ESCALATED
    assert transition(FindingStatus.ESCALATED, "ALLOW", 9) is FindingStatus.RESOLVED


def test_clean_result_after_a_finding_resolves_it():
    assert transition(FindingStatus.PERSISTING, "ALLOW", 4) is FindingStatus.RESOLVED


def test_clean_result_on_something_never_flagged_is_not_a_finding():
    """Otherwise every healthy record would enter the digest as a non-event."""
    assert transition(None, "ALLOW", 1) is None


def test_already_resolved_and_still_clean_reports_nothing():
    assert transition(FindingStatus.RESOLVED, "ALLOW", 5) is None


def test_a_resolved_finding_that_recurs_is_new_again():
    """The condition came back. That is new information, not a continuation."""
    assert transition(FindingStatus.RESOLVED, "BLOCK", 6) is FindingStatus.NEW


@pytest.mark.parametrize("gate_result", ["BLOCK", "NEEDS_REVIEW"])
def test_needs_review_is_treated_as_unresolved(gate_result):
    assert transition(None, gate_result, 1) is FindingStatus.NEW


def test_transition_is_deterministic():
    args = (FindingStatus.NEW, "NEEDS_REVIEW", 2)
    assert transition(*args) is transition(*args)


def test_persisting_does_not_re_alert():
    """PERSISTING is visible in the digest but must not surface as an alert --
    that distinction is the entire purpose of this module."""
    assert is_announceable(FindingStatus.NEW) is True
    assert is_announceable(FindingStatus.ESCALATED) is True
    assert is_announceable(FindingStatus.RESOLVED) is True
    assert is_announceable(FindingStatus.PERSISTING) is False
    assert is_announceable(None) is False
