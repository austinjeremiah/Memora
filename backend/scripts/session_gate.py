"""SESSION 2 -- fresh process. The full memory -> evidence -> gate pipeline.

Same patient, same claim set, TWO different clinicians. The gate's verdict
changes with the role, because authority is part of the decision -- not a
presentation detail applied afterwards.

The claim list is a FIXED ADVERSARIAL INPUT, not a stand-in for the model.
Sibyl is real throughout. Phase 13 swaps this list for live Groq output.

Usage: MEMORA_DB=/path/to/memory.db python scripts/session_gate.py [PATIENT_ID]
"""

import os
import sys
import time
from pathlib import Path

from memora.config import settings

if os.environ.get("MEMORA_DB"):
    settings.sibyl_db_path = Path(os.environ["MEMORA_DB"])

from memora.context.situations import ClinicianRole
from memora.evidence.resolver import resolve_all
from memora.gate.gate import GateResult, evaluate_all, summarise
from memora.ontology.kinds import KIND_ALLERGY, KIND_LAB_TREND, KIND_MEDICATION
from memora.sibyl.client import PatientMemory

PATIENT = sys.argv[1] if len(sys.argv) > 1 else "P-10482"

PROPOSED = [
    {"text": "Drug B is the patient's current active medication",
     "related_kind": KIND_MEDICATION, "related_name": "drug_b"},
    {"text": "Drug A may be restarted on the ward",
     "related_kind": KIND_MEDICATION, "related_name": "drug_a"},
    {"text": "Creatinine is rising and needs monitoring",
     "related_kind": KIND_LAB_TREND, "related_name": "creatinine"},
    {"text": "Patient has a documented penicillin allergy",
     "related_kind": KIND_ALLERGY, "related_name": "penicillin"},
    {"text": "Patient tolerated Drug Z well",
     "related_kind": KIND_MEDICATION, "related_name": "drug_z"},
    {"text": "Patient is ready for discharge with no outstanding concerns"},
]

MARK = {GateResult.ALLOW: "ALLOW ", GateResult.NEEDS_REVIEW: "REVIEW",
        GateResult.BLOCK: "BLOCK "}

print(f"=== SESSION 2 @ {time.strftime('%Y-%m-%d %H:%M:%S')} · pid {os.getpid()} ===")
print("    fresh process -- every verdict below came from disk\n")

memory = PatientMemory(PATIENT, require_data=True)
checks = resolve_all(memory, PROPOSED)

for role in (ClinicianRole.ICU_PHYSICIAN, ClinicianRole.SURGEON):
    decisions = evaluate_all(memory, checks, role)
    print(f"┌─ as {role.value}")
    for decision in decisions:
        print(f"│ [{MARK[decision.result]}] {decision.evidence.claim_text[:56]}")
        if decision.triggered_rules:
            print(f"│           rules: {', '.join(decision.triggered_rules)}")
        elif decision.result is GateResult.BLOCK:
            print(f"│           {decision.reason[:70]}")
    print(f"└─ {summarise(decisions)}\n")

icu = evaluate_all(memory, checks, ClinicianRole.ICU_PHYSICIAN)
surgeon = evaluate_all(memory, checks, ClinicianRole.SURGEON)
assert [d.result for d in icu] != [d.result for d in surgeon], \
    "role made no difference -- authority is not being enforced"
assert not any(d.result is GateResult.ALLOW and not d.evidence.supported for d in icu), \
    "a claim was ALLOWed without evidence"
print("=== SESSION 2 OK -- gate is role-aware and cannot allow without evidence ===")
