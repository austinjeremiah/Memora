"""Ingestion: real Synthea bundles -> Sibyl memory.

Two constraints shape this, both measured rather than assumed:

  * VOLUME. A single real Synthea patient parses to ~450 events, of which
    ~240 are lab observations -- 60 bundles were 58 MB of FHIR. Sibyl's
    free tier caps the store at 5,242,880 bytes and an empty store already
    costs ~266 KB, so everything cannot go in. Labs are capped per test to the
    most recent few, which is also the clinically useful part: a trend needs
    recent points, not a decade of them.

  * STATUS. Real MedicationRequest.status is only "active" or "completed",
    never "stopped", so there is no discontinued signal to read. Conditions do
    carry active/resolved. Status is taken from the source resource where it
    exists and left unset where it does not, rather than invented.
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from memora.gate.gate import GateResult
from memora.ingest.change_detector import ChangeType, apply_fact_change
from memora.ingest.synthea_parser import parse_patient_bundle
from memora.ontology.events import (
    EVENT_LAB_RESULT,
    SEVERITY_CRITICAL,
    ClinicalEvent,
)
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_CARE_PHASE,
    KIND_DIAGNOSIS,
    KIND_LAB_TREND,
    KIND_MEDICATION,
    KIND_PROCEDURE,
)
from memora.sentinel.scan import evaluate_delta
from memora.sibyl.client import PatientMemory

log = logging.getLogger("memora.ingest")

# Retention is per DISTINCT RECORD, not global, because the cost driver is row
# count rather than payload. Measured on three real patients: 999 journal rows
# and 272 entities held only 410 KB of actual content, while the store was
# 4.3 MB -- SQLite plus the four FTS5 indexes cost roughly 10x the payload. So
# trimming repeats buys far more headroom than trimming detail does, which is
# why every retained record keeps its full structured body.
#
# 340 of those 999 rows were repeat procedures across just 67 distinct
# procedures. The tenth identical "Assessment of health and social care needs"
# tells a receiving clinician nothing the first three did not.
MAX_LAB_POINTS_PER_TEST = 5      # enough points to compute a real trend
MAX_EVENTS_PER_RECORD = 3        # repeats of any other single record

# Absolute ceiling per patient, as a backstop.
MAX_EVENTS_PER_PATIENT = 400

STATUS_FOR_KIND = {
    KIND_MEDICATION: "active",
    KIND_ALLERGY: "documented",
    KIND_DIAGNOSIS: "active",
    KIND_PROCEDURE: "performed",
    KIND_LAB_TREND: "active",
    KIND_CARE_PHASE: "recorded",
}


@dataclass
class SentinelHit:
    """A Sentinel decision raised during ingestion, buffered not written.

    Findings are collected in memory and flushed to the digest ONCE by the
    caller, rather than each hook writing its own -- one set_state per run, not
    one per changed fact, consistent with the row-count discipline the store
    size measurements forced.
    """

    kind: str
    name: str
    gate_result: str
    reason: str
    triggered_rules: list[str] = field(default_factory=list)


@dataclass
class IngestReport:
    patient_id: str
    events_parsed: int = 0
    events_written: int = 0
    facts_new: int = 0
    facts_confirmed: int = 0
    facts_changed: int = 0
    db_size_bytes: int = 0
    pct_of_cap: float = 0.0
    kinds: dict[str, int] = field(default_factory=dict)
    sentinel_hits: list[SentinelHit] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "events_parsed": self.events_parsed,
            "events_written": self.events_written,
            "facts": {"new": self.facts_new, "confirmed": self.facts_confirmed,
                      "changed": self.facts_changed},
            "kinds": self.kinds,
            "sentinel_hits": len(self.sentinel_hits),
            "db_size_bytes": self.db_size_bytes,
            "pct_of_cap": round(self.pct_of_cap, 2),
        }


def _fact_body(event: ClinicalEvent) -> dict:
    """The WARM payload for a non-lab fact.

    Carries the source record's structured detail -- codes, dates, categories,
    criticality -- not just a rendered sentence. A clinician asking "what is
    this, exactly" should get an answer from memory rather than from prose.
    """
    body: dict = {"label": event.summary, "last_seen": event.timestamp}
    if event.details:
        body.update(event.details)
    return body


def build_lab_trend(points: list[ClinicalEvent]) -> dict:
    """Fold repeated observations of one test into a trajectory.

    This is the clearest thing persistent memory buys: a single result is a
    number, but the same store holding every result is a TREND -- and a rising
    creatinine is a different clinical fact from a creatinine of 1.61. The
    direction is computed from the retained series, so the entity answers
    "what is happening to this value" and not merely "what was it last".
    """
    ordered = sorted(points, key=lambda e: e.timestamp)
    series = [
        {"value": e.details["value"], "at": e.timestamp[:10]}
        for e in ordered if e.details and e.details.get("value") is not None
    ]
    latest = ordered[-1]
    detail = latest.details or {}

    direction, delta = "single_reading", None
    if len(series) >= 2:
        first_value, last_value = series[0]["value"], series[-1]["value"]
        try:
            delta = round(float(last_value) - float(first_value), 4)
            scale = abs(float(first_value)) or 1.0
            if abs(delta) / scale < 0.05:
                direction = "stable"
            else:
                direction = "rising" if delta > 0 else "falling"
        except (TypeError, ValueError):
            direction, delta = "unknown", None

    return {
        "test": detail.get("test", latest.related_name),
        "loinc": detail.get("loinc"),
        "unit": detail.get("unit"),
        "latest_value": detail.get("value"),
        "latest_at": latest.timestamp[:10],
        "readings": len(series),
        "series": series,
        "direction": direction,
        "delta": delta,
        "label": latest.summary,
        "last_seen": latest.timestamp,
    }


def select_events(events: list[ClinicalEvent]) -> list[ClinicalEvent]:
    """Trim to what fits and what matters, deterministically.

    Labs are thinned per test, everything else is kept. If the result still
    exceeds the per-patient ceiling, the OLDEST plain events are dropped first
    while every critical event is retained -- losing a documented drug allergy
    to a volume cap would defeat the entire product.
    """
    seen: dict[tuple[str, str], int] = defaultdict(int)
    kept: list[ClinicalEvent] = []

    for event in sorted(events, key=lambda e: e.timestamp, reverse=True):
        # Never thin a critical event. Losing a documented drug allergy to a
        # retention rule would defeat the entire product.
        if event.severity == SEVERITY_CRITICAL:
            kept.append(event)
            continue

        key = (event.related_kind or "", event.related_name or "unknown")
        ceiling = (MAX_LAB_POINTS_PER_TEST
                   if event.event_type == EVENT_LAB_RESULT
                   else MAX_EVENTS_PER_RECORD)
        if seen[key] >= ceiling:
            continue
        seen[key] += 1
        kept.append(event)

    if len(kept) > MAX_EVENTS_PER_PATIENT:
        critical = [e for e in kept if e.severity == SEVERITY_CRITICAL]
        others = [e for e in kept if e.severity != SEVERITY_CRITICAL]
        room = max(0, MAX_EVENTS_PER_PATIENT - len(critical))
        kept = critical + others[:room]

    kept.sort(key=lambda e: e.timestamp)
    return kept


def ingest_patient(bundle_path: Path, patient_id: str | None = None) -> IngestReport:
    """Parse one bundle and write it into Sibyl.

    Every event becomes a journal entry. Every event carrying a record pointer
    also maintains the corresponding WARM fact -- the pair is the point: the
    journal says what happened, the entity says what is true now, and neither
    alone is sufficient.
    """
    parsed_id, events = parse_patient_bundle(bundle_path)
    patient_id = patient_id or parsed_id

    memory = PatientMemory(patient_id)
    report = IngestReport(patient_id=patient_id, events_parsed=len(events))

    selected = select_events(events)
    kind_counts: dict[str, int] = defaultdict(int)

    # Labs are folded into one trend entity per test; everything else maps
    # one event to one fact. Every observation is still journalled either way,
    # so COLD stays complete while WARM holds the computed trajectory.
    lab_points: dict[str, list[ClinicalEvent]] = defaultdict(list)

    for event in selected:
        kind, name = event.related_kind, event.related_name

        if kind == KIND_LAB_TREND and name:
            lab_points[name].append(event)
            memory.log_event(event)
            report.events_written += 1
            continue

        if kind and name:
            status = STATUS_FOR_KIND.get(kind)
            result = apply_fact_change(memory, kind, name, _fact_body(event),
                                       event, status=status)
            if result.change is ChangeType.NEW:
                report.facts_new += 1
                kind_counts[kind] += 1
            elif result.change is ChangeType.CONFIRMED:
                report.facts_confirmed += 1
                # A confirmed fact writes no transition, so the observation
                # that would otherwise be lost is journalled explicitly.
                memory.log_event(event)
            else:
                report.facts_changed += 1
                # THE SENTINEL HOOK. This is the one place a WARM change is
                # already known, so the previous and current bodies are handed
                # straight over rather than re-derived. No LLM is reachable
                # from here.
                decision = evaluate_delta(
                    memory, kind, name,
                    previous=result.previous_body, current=_fact_body(event),
                    previous_status=result.previous_status,
                    current_status=result.new_status,
                    event_severity=event.severity,
                )
                if decision is not None and decision.result is not GateResult.ALLOW:
                    report.sentinel_hits.append(SentinelHit(
                        kind=kind, name=name,
                        gate_result=decision.result.value,
                        reason=decision.reason,
                        triggered_rules=list(decision.triggered_rules),
                    ))
        else:
            memory.log_event(event)
        report.events_written += 1

    for name, points in lab_points.items():
        trend = build_lab_trend(points)
        result = apply_fact_change(memory, KIND_LAB_TREND, name, trend,
                                   points[-1], status=STATUS_FOR_KIND[KIND_LAB_TREND])
        if result.change is ChangeType.NEW:
            report.facts_new += 1
            kind_counts[KIND_LAB_TREND] += 1
        elif result.change is ChangeType.CONFIRMED:
            report.facts_confirmed += 1
        else:
            report.facts_changed += 1

    quota = memory.quota()
    report.db_size_bytes = quota["db_size_bytes"]
    report.pct_of_cap = 100 * (quota.get("pct_used") or 0)
    report.kinds = dict(kind_counts)
    log.info("ingested %s: %s", patient_id, report.as_dict())
    return report


def find_story_patients(fhir_dir: Path, min_drug_allergies: int = 1,
                        min_medications: int = 3,
                        min_encounters: int = 5) -> list[dict]:
    """Pick demo patients deliberately.

    Filters on DRUG allergies specifically. Only 7 of 60 generated patients had
    any AllergyIntolerance at all and fewer still had a medication-category
    one, so a story patient has to be selected on real content rather than
    taking the first N bundles.
    """
    candidates = []
    for path in sorted(Path(fhir_dir).glob("*.json")):
        bundle = json.loads(path.read_text())
        drug_allergies, medications, encounters = [], set(), 0
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            rtype = resource.get("resourceType")
            if rtype == "AllergyIntolerance" and "medication" in (resource.get("category") or []):
                drug_allergies.append(
                    (resource.get("code") or {}).get("text", "unknown"))
            elif rtype == "MedicationRequest":
                medications.add(
                    (resource.get("medicationCodeableConcept") or {}).get("text", "?"))
            elif rtype == "Encounter":
                encounters += 1
        if (len(drug_allergies) >= min_drug_allergies
                and len(medications) >= min_medications
                and encounters >= min_encounters):
            candidates.append({
                "path": str(path),
                "drug_allergies": drug_allergies,
                "medications": len(medications),
                "encounters": encounters,
            })
    candidates.sort(key=lambda c: (-len(c["drug_allergies"]), -c["encounters"]))
    return candidates
