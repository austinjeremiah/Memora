"""Synthea FHIR R4 -> MEMORA clinical events.

Field paths here were read off real Synthea output (60 generated bundles),
not taken from the FHIR spec or assumed. Things that only show up in real data:

  * `medicationCodeableConcept.text` is sometimes ABSENT. Falling back to
    `coding[0].display` is required, or those medications parse as "?" and
    collapse into one entity. Observed on real bundles.
  * `MedicationRequest.status` is "active" or "completed" -- never "stopped".
    So there is no discontinued-medication signal to read; deriving one by
    string-matching "discontinu" in a summary (as an earlier draft did) finds
    nothing at all in real data.
  * `Condition.clinicalStatus.coding[0].code` is a genuine active/resolved
    signal and maps straight onto the entity status column.
  * `Procedure` uses `performedPeriod.start`; `performedDateTime` is rare.
  * `AllergyIntolerance` carries `category` (medication/food/environment) and
    `criticality`, which is what makes a drug allergy distinguishable.
  * Only 7 of 60 generated patients had any AllergyIntolerance at all -- it is
    probabilistic, so a story patient has to be selected, not assumed.

Deliberately narrow: seven resource types, chosen because they carry the
ICU-to-ward reconciliation story. Not a general FHIR importer.
"""

import json
from pathlib import Path
from typing import Any

from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_DIAGNOSIS_MADE,
    EVENT_HANDOFF,
    EVENT_LAB_RESULT,
    EVENT_MEDICATION_ADMINISTERED,
    EVENT_PROCEDURE_PERFORMED,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
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

# Identifier characters Sibyl refuses on write.
_UNSAFE = set(';<>|"`\\')


def _text(concept: dict[str, Any] | None, default: str = "unknown") -> str:
    """CodeableConcept -> display text.

    `.text` is missing on some real resources, so `coding[0].display` is a
    required fallback rather than a nicety.
    """
    if not isinstance(concept, dict):
        return default
    if concept.get("text"):
        return str(concept["text"])
    for coding in concept.get("coding") or []:
        if coding.get("display"):
            return str(coding["display"])
        if coding.get("code"):
            return str(coding["code"])
    return default


def _code(concept: dict[str, Any] | None) -> str | None:
    for coding in (concept or {}).get("coding") or []:
        if coding.get("code"):
            return str(coding["code"])
    return None


def slug(text: str, limit: int = 60) -> str:
    """A search-friendly, Sibyl-safe entity name.

    Sibyl validates identifiers on write and rejects shell metacharacters, and
    real medication names contain brackets, slashes and percent signs, so this
    filters rather than only substituting spaces.
    """
    cleaned = "".join("_" if ch in _UNSAFE or ch.isspace() else ch
                      for ch in text.strip().lower())
    for ch in "[]{}()":
        cleaned = cleaned.replace(ch, "")
    cleaned = cleaned.replace("/", "_").replace(",", "")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")[:limit] or "unknown"


def _when(resource: dict[str, Any], *paths: str) -> str:
    """First present timestamp among the given paths, dotted for nesting."""
    for path in paths:
        node: Any = resource
        for part in path.split("."):
            node = node.get(part) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, str) and node:
            return node
    return ""


def parse_patient_bundle(path: Path) -> tuple[str, list[ClinicalEvent]]:
    """Return (patient_id, chronologically ordered events)."""
    bundle = json.loads(Path(path).read_text())
    entries = bundle.get("entry", [])

    patient = next(
        (e["resource"] for e in entries if e["resource"]["resourceType"] == "Patient"),
        None,
    )
    if patient is None:
        raise ValueError(f"{path} contains no Patient resource")
    patient_id = str(patient["id"])

    events: list[ClinicalEvent] = []
    for entry in entries:
        event = _parse_resource(entry.get("resource") or {})
        if event is not None:
            events.append(event)

    events = [e for e in events if e.timestamp]
    events.sort(key=lambda e: e.timestamp)
    return patient_id, events


def _parse_resource(resource: dict[str, Any]) -> ClinicalEvent | None:
    rtype = resource.get("resourceType")

    if rtype == "MedicationRequest":
        name = _text(resource.get("medicationCodeableConcept"), "unknown medication")
        return ClinicalEvent(
            event_type=EVENT_MEDICATION_ADMINISTERED,
            summary=f"{name} prescribed",
            timestamp=_when(resource, "authoredOn"),
            related_kind=KIND_MEDICATION,
            related_name=slug(name),
            source_id=str(resource.get("id", "")),
            severity=SEVERITY_INFO,
        )

    if rtype == "MedicationAdministration":
        name = _text(resource.get("medicationCodeableConcept"), "unknown medication")
        return ClinicalEvent(
            event_type=EVENT_MEDICATION_ADMINISTERED,
            summary=f"{name} administered",
            timestamp=_when(resource, "effectiveDateTime", "effectivePeriod.start"),
            related_kind=KIND_MEDICATION,
            related_name=slug(name),
            source_id=str(resource.get("id", "")),
            severity=SEVERITY_INFO,
        )

    if rtype == "AllergyIntolerance":
        name = _text(resource.get("code"), "unspecified allergen")
        categories = resource.get("category") or []
        criticality = resource.get("criticality")
        is_drug = "medication" in categories
        return ClinicalEvent(
            event_type=EVENT_ADVERSE_REACTION,
            summary=(f"Documented {'drug ' if is_drug else ''}allergy: {name}"
                     f" ({', '.join(categories) or 'uncategorised'},"
                     f" criticality {criticality or 'unknown'})"),
            timestamp=_when(resource, "recordedDate", "onsetDateTime"),
            related_kind=KIND_ALLERGY,
            related_name=slug(name),
            source_id=str(resource.get("id", "")),
            # A drug allergy is what can actually contraindicate a prescription.
            severity=SEVERITY_CRITICAL if is_drug else SEVERITY_WARNING,
        )

    if rtype == "Condition":
        name = _text(resource.get("code"), "unspecified condition")
        return ClinicalEvent(
            event_type=EVENT_DIAGNOSIS_MADE,
            summary=f"{name} ({_code(resource.get('clinicalStatus')) or 'unknown'})",
            timestamp=_when(resource, "recordedDate", "onsetDateTime"),
            related_kind=KIND_DIAGNOSIS,
            related_name=slug(name),
            source_id=str(resource.get("id", "")),
            severity=SEVERITY_INFO,
        )

    if rtype == "Procedure":
        name = _text(resource.get("code"), "unspecified procedure")
        return ClinicalEvent(
            event_type=EVENT_PROCEDURE_PERFORMED,
            summary=name,
            timestamp=_when(resource, "performedDateTime", "performedPeriod.start"),
            related_kind=KIND_PROCEDURE,
            related_name=slug(name),
            source_id=str(resource.get("id", "")),
            severity=SEVERITY_INFO,
        )

    if rtype == "Observation":
        value = resource.get("valueQuantity")
        if not isinstance(value, dict) or value.get("value") is None:
            return None  # non-numeric observations are not a lab trend
        name = _text(resource.get("code"), "unspecified observation")
        return ClinicalEvent(
            event_type=EVENT_LAB_RESULT,
            summary=f"{name}: {value['value']} {value.get('unit', '')}".strip(),
            timestamp=_when(resource, "effectiveDateTime", "issued"),
            related_kind=KIND_LAB_TREND,
            related_name=slug(name),
            source_id=str(resource.get("id", "")),
            severity=SEVERITY_INFO,
        )

    if rtype == "Encounter":
        types = resource.get("type") or [{}]
        name = _text(types[0] if types else None, "encounter")
        encounter_class = (resource.get("class") or {}).get("code", "")
        return ClinicalEvent(
            event_type=EVENT_HANDOFF,
            summary=f"{name} ({encounter_class or 'unspecified'})",
            timestamp=_when(resource, "period.start"),
            related_kind=KIND_CARE_PHASE,
            related_name=slug(name),
            source_id=str(resource.get("id", "")),
            severity=SEVERITY_INFO,
        )

    return None


def resource_status(resource: dict[str, Any]) -> str | None:
    """The entity `status` column value implied by a FHIR resource."""
    rtype = resource.get("resourceType")
    if rtype in ("Condition", "AllergyIntolerance"):
        return _code(resource.get("clinicalStatus"))
    if rtype in ("MedicationRequest", "MedicationAdministration", "Procedure"):
        return resource.get("status")
    return None
