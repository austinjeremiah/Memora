"""SESSION 1 -- writes a patient's ICU history into Sibyl, then EXITS.

Nothing is shared with the reader process except memory.db on disk.
Usage: MEMORA_DB=/path/to/memory.db python scripts/session_write.py [PATIENT_ID]

NOTE: the clinical story below is seed scaffolding for the cross-process proof.
Phase 7-8 replaces it with real Synthea FHIR bundles parsed by the ingestion
pipeline. The Sibyl writes themselves are already real.
"""

import os
import sys
import time
from pathlib import Path

from memora.config import settings

if os.environ.get("MEMORA_DB"):
    settings.sibyl_db_path = Path(os.environ["MEMORA_DB"])

from sibyl_memory_client import MemoryClient

from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_COMPLICATION,
    EVENT_DIAGNOSIS_MADE,
    EVENT_LAB_RESULT,
    EVENT_MEDICATION_ADMINISTERED,
    EVENT_MEDICATION_DISCONTINUED,
    EVENT_PROCEDURE_PERFORMED,
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
    ClinicalEvent,
)
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_DIAGNOSIS,
    KIND_LAB_TREND,
    KIND_MEDICATION,
    KIND_PROCEDURE,
    STATUS_ACTIVE,
    STATUS_CONTRAINDICATED,
    STATUS_DOCUMENTED,
    STATUS_PERFORMED,
)
from memora.sibyl.client import PatientMemory

PATIENT = sys.argv[1] if len(sys.argv) > 1 else "P-10482"

MemoryClient.local(str(settings.sibyl_db_path))  # ensure the store exists

print(f"=== SESSION 1 @ {time.strftime('%Y-%m-%d %H:%M:%S')} · pid {os.getpid()} ===")
print(f"    store:   {settings.sibyl_db_path}")
print(f"    patient: {PATIENT}")

m = PatientMemory(PATIENT)

FACTS = [
    (KIND_DIAGNOSIS, "sepsis", {"onset": "2026-01-01"}, STATUS_ACTIVE),
    (KIND_MEDICATION, "drug_a", {"reason": "documented adverse reaction on 2026-01-04"},
     STATUS_CONTRAINDICATED),
    (KIND_MEDICATION, "drug_b", {"dose": "5mg BD"}, STATUS_ACTIVE),
    (KIND_ALLERGY, "penicillin", {"reaction": "anaphylaxis"}, STATUS_DOCUMENTED),
    (KIND_LAB_TREND, "creatinine", {"latest": "2.1", "trend": "rising"}, STATUS_ACTIVE),
    (KIND_PROCEDURE, "central_line", {"site": "right IJ"}, STATUS_PERFORMED),
]

EVENTS = [
    ClinicalEvent(EVENT_DIAGNOSIS_MADE, "Sepsis diagnosed on admission",
                  "2026-01-01T09:00:00Z", KIND_DIAGNOSIS, "sepsis", "fhir-cond-1"),
    ClinicalEvent(EVENT_MEDICATION_ADMINISTERED, "Drug A administered",
                  "2026-01-02T08:00:00Z", KIND_MEDICATION, "drug_a", "fhir-med-1"),
    ClinicalEvent(EVENT_PROCEDURE_PERFORMED, "Central line placed, right IJ",
                  "2026-01-03T11:00:00Z", KIND_PROCEDURE, "central_line", "fhir-proc-4"),
    ClinicalEvent(EVENT_ADVERSE_REACTION, "Documented adverse reaction to Drug A",
                  "2026-01-04T14:30:00Z", KIND_MEDICATION, "drug_a", "fhir-air-7",
                  SEVERITY_CRITICAL),
    ClinicalEvent(EVENT_MEDICATION_DISCONTINUED, "Drug A discontinued after reaction",
                  "2026-01-04T16:00:00Z", KIND_MEDICATION, "drug_a", "fhir-med-9",
                  SEVERITY_CRITICAL),
    ClinicalEvent(EVENT_COMPLICATION, "Acute kidney injury, creatinine rising",
                  "2026-01-05T05:00:00Z", KIND_LAB_TREND, "creatinine", "fhir-cond-8",
                  SEVERITY_WARNING),
    ClinicalEvent(EVENT_LAB_RESULT, "Creatinine 2.1 mg/dL (rising)",
                  "2026-01-05T06:00:00Z", KIND_LAB_TREND, "creatinine", "fhir-obs-12"),
]

for kind, name, body, status in FACTS:
    m.set_fact(kind, name, body, status=status)
for event in EVENTS:
    m.log_event(event)

print(f"    wrote {len(FACTS)} warm facts + {len(EVENTS)} journal events")
print(f"    store now {m.quota()['db_size_bytes']:,} bytes "
      f"({100 * m.quota()['pct_used']:.2f}% of the free-tier cap)")
print("=== SESSION 1 TERMINATING -- this process is now dead ===")
