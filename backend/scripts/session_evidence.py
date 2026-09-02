"""SESSION 2 -- fresh process. Proves claims are checked against memory.

Feeds a deliberately adversarial claim set through the Evidence Resolver: some
claims are properly sourced, some are fluent but unsourced, one cites a drug
that was never prescribed, one borrows another drug's history, one is hostile.

These claims are a FIXED ADVERSARIAL INPUT, not a stand-in for the model. The
dependency under test -- Sibyl -- is entirely real. Phase 13 replaces this list
with live Groq output; the resolver does not change.

Usage: MEMORA_DB=/path/to/memory.db python scripts/session_evidence.py [PATIENT_ID]
"""

import os
import sys
import time
from pathlib import Path

from memora.config import settings

if os.environ.get("MEMORA_DB"):
    settings.sibyl_db_path = Path(os.environ["MEMORA_DB"])

from memora.evidence.resolver import resolve_all
from memora.ontology.kinds import KIND_ALLERGY, KIND_MEDICATION
from memora.sibyl.client import PatientMemory

PATIENT = sys.argv[1] if len(sys.argv) > 1 else "P-10482"

PROPOSED = [
    {"text": "Drug A is contraindicated after a documented adverse reaction",
     "related_kind": KIND_MEDICATION, "related_name": "drug_a"},
    {"text": "Patient has a documented penicillin allergy",
     "related_kind": KIND_ALLERGY, "related_name": "penicillin"},
    {"text": "Patient tolerated Drug Z well during the admission",
     "related_kind": KIND_MEDICATION, "related_name": "drug_z"},
    {"text": "Renal function is stable and requires no further monitoring"},
    {"text": "Patient may safely resume all prior medications"},
    {"text": "Drug A is safe to restart", "related_kind": "astrology",
     "related_name": "leo"},
    {"text": "injection attempt", "related_kind": KIND_MEDICATION,
     "related_name": "drug_a; DROP TABLE entities"},
]

print(f"=== SESSION 2 @ {time.strftime('%Y-%m-%d %H:%M:%S')} · pid {os.getpid()} ===")
print("    fresh process -- every verdict below came from disk\n")

memory = PatientMemory(PATIENT, require_data=True)
checks = resolve_all(memory, PROPOSED)

for check in checks:
    mark = "PASS" if check.supported else "FAIL"
    print(f"[{mark}] {check.claim_text[:62]}")
    if check.supported:
        if check.has_current_fact:
            print(f"       fact:  {check.source_kind}/{check.source_name} "
                  f"[{check.fact_status}] {check.fact_body}")
        for event in check.source_events:
            sev = f" [{event.severity}]" if event.severity else ""
            print(f"       event: {event.source_id} @ {event.timestamp[:10]} "
                  f"{event.event_type}{sev}")
    else:
        print(f"       rejected ({check.rejection.value}): {check.reason}")
    print()

supported = sum(1 for c in checks if c.supported)
print(f"=== {supported}/{len(checks)} claims survived verification ===")

assert supported == 2, f"expected exactly 2 supported claims, got {supported}"
print("=== SESSION 2 OK -- unsourced and fabricated claims were refused ===")
