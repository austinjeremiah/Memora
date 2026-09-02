"""SESSION 2 -- fresh process. The same evidence, judged for two clinicians.

One patient, one set of model-proposed claims, checked once against memory,
then put through the gate for a ward physician and for a surgeon. The verdicts
differ because authority is part of the decision, not presentation applied
afterwards: a pre-operative surgeon has no business reading a lab trend or a
psychiatric diagnosis, and the gate enforces that on identical evidence.

Usage: MEMORA_DB=/path/to/memory.db python scripts/session_gate.py [PATIENT]
"""

import os
import sys
import time
from pathlib import Path

from memora.config import settings

if os.environ.get("MEMORA_DB"):
    settings.sibyl_db_path = Path(os.environ["MEMORA_DB"])

from memora.clinicians.roles import get_clinician
from memora.context.engine import compile_plan, execute_plan
from memora.context.situations import Situation
from memora.evidence.resolver import resolve_all
from memora.gate.gate import GateResult, evaluate_all, summarise
from memora.llm.propose import propose_claims
from memora.sibyl.client import PatientMemory

PATIENT = sys.argv[1] if len(sys.argv) > 1 else "P-10482"
WARD = get_clinician("dr_arun")
SURGEON = get_clinician("dr_priya")

MARK = {GateResult.ALLOW: "ALLOW ", GateResult.NEEDS_REVIEW: "REVIEW",
        GateResult.BLOCK: "BLOCK "}

print(f"=== SESSION 2 @ {time.strftime('%Y-%m-%d %H:%M:%S')} · pid {os.getpid()} ===")
print("    fresh process -- claims proposed once, judged twice\n")

context = execute_plan(compile_plan(PATIENT, Situation.ICU_TO_WARD, WARD.role))
proposed = propose_claims(context)

memory = PatientMemory(PATIENT)
checks = resolve_all(memory, proposed)
print(f"{len(proposed)} claims proposed, "
      f"{sum(1 for c in checks if c.supported)} supported by memory\n")

ward = evaluate_all(memory, checks, WARD.role)
surgeon = evaluate_all(memory, checks, SURGEON.role)

print(f"{'CLAIM':<52} {'WARD':<7} {'SURGEON'}")
print("-" * 72)
divergent = 0
for check, w, s in zip(checks, ward, surgeon, strict=True):
    if w.result is not s.result:
        divergent += 1
    flag = " <-- differs" if w.result is not s.result else ""
    print(f"{check.claim_text[:50]:<52} {MARK[w.result]:<7} {MARK[s.result]}{flag}")

print()
print(f"ward physician : {summarise(ward)}")
print(f"surgeon        : {summarise(surgeon)}")
print(f"\n{divergent} claims judged differently on identical evidence")

for check, s in zip(checks, surgeon, strict=True):
    if s.result is GateResult.BLOCK and check.supported:
        print(f"\nexample: {s.reason}")
        break

assert [d.result for d in ward] != [d.result for d in surgeon], \
    "role made no difference -- authority is not being enforced"
print("\n=== SESSION 2 OK -- same evidence, role-dependent verdicts ===")
