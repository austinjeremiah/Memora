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

from memora.ingest.change_detector import ChangeType, apply_fact_change
from memora.ingest.synthea_parser import parse_patient_bundle
from memora.ontology.events import EVENT_LAB_RESULT, ClinicalEvent
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_CARE_PHASE,
    KIND_DIAGNOSIS,
    KIND_LAB_TREND,
    KIND_MEDICATION,
    KIND_PROCEDURE,
)
from memora.sibyl.client import PatientMemory

log = logging.getLogger("memora.ingest")

# Most recent N results per distinct lab test. Labs are ~53% of parsed events
# on a real patient and would otherwise dominate the store.
MAX_LAB_POINTS_PER_TEST = 3

# Journal entries per patient. A hard ceiling so one unusually long history
# cannot consume the whole free-tier budget.
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

    def as_dict(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "events_parsed": self.events_parsed,
            "events_written": self.events_written,
            "facts": {"new": self.facts_new, "confirmed": self.facts_confirmed,
                      "changed": self.facts_changed},
            "kinds": self.kinds,
            "db_size_bytes": self.db_size_bytes,
            "pct_of_cap": round(self.pct_of_cap, 2),
        }


def select_events(events: list[ClinicalEvent]) -> list[ClinicalEvent]:
    """Trim to what fits and what matters, deterministically.

    Labs are thinned per test, everything else is kept. If the result still
    exceeds the per-patient ceiling, the OLDEST plain events are dropped first
    while every critical event is retained -- losing a documented drug allergy
    to a volume cap would defeat the entire product.
    """
    lab_seen: dict[str, int] = defaultdict(int)
    kept: list[ClinicalEvent] = []

    for event in sorted(events, key=lambda e: e.timestamp, reverse=True):
        if event.event_type == EVENT_LAB_RESULT:
            key = event.related_name or "unknown"
            if lab_seen[key] >= MAX_LAB_POINTS_PER_TEST:
                continue
            lab_seen[key] += 1
        kept.append(event)

    if len(kept) > MAX_EVENTS_PER_PATIENT:
        critical = [e for e in kept if e.severity == "critical"]
        others = [e for e in kept if e.severity != "critical"]
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

    for event in selected:
        kind, name = event.related_kind, event.related_name
        if kind and name:
            status = STATUS_FOR_KIND.get(kind)
            body = {"label": event.summary, "last_seen": event.timestamp}
            result = apply_fact_change(memory, kind, name, body, event, status=status)
            if result.change is ChangeType.NEW:
                report.facts_new += 1
                kind_counts[kind] += 1
            elif result.change is ChangeType.CONFIRMED:
                report.facts_confirmed += 1
                # A confirmed fact writes nothing, so the journal entry that
                # would otherwise be lost is written explicitly.
                memory.log_event(event)
            else:
                report.facts_changed += 1
        else:
            memory.log_event(event)
        report.events_written += 1

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
