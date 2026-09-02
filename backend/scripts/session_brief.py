"""SESSION 2 -- fresh process. The complete MEMORA pipeline, end to end.

  Sibyl memory -> Context Engine -> LLM proposal -> Evidence Resolver -> Gate

A real model reads real recalled memory and proposes real claims, and every one
of them is checked against the record before it can be presented. Nothing here
is simulated.

Usage: MEMORA_DB=/path/to/memory.db python scripts/session_brief.py [PATIENT] [CLINICIAN]
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
CLINICIAN = get_clinician(sys.argv[2] if len(sys.argv) > 2 else "dr_arun")

MARK = {GateResult.ALLOW: "ALLOW ", GateResult.NEEDS_REVIEW: "REVIEW",
        GateResult.BLOCK: "BLOCK "}

print(f"=== SESSION 2 @ {time.strftime('%Y-%m-%d %H:%M:%S')} · pid {os.getpid()} ===")
print(f"    {CLINICIAN.name} ({CLINICIAN.role.value}) · ICU -> ward handover")
print("    fresh process -- all patient context recalled from disk\n")

plan = compile_plan(PATIENT, Situation.ICU_TO_WARD, CLINICIAN.role)
context = execute_plan(plan)
print(f"[1] recalled {context.fact_count()} facts, {len(context.history)} events")

# Surface what persistent memory actually holds: not last values, trajectories.
ARROW = {"rising": "^ RISING ", "falling": "v FALLING", "stable": "= STABLE ",
         "single_reading": "  single "}
trends = [r for r in context.facts.get("lab_trend", [])
          if (r["body"].get("readings") or 0) >= 2]
if trends:
    print(f"\n    trajectories held in memory ({len(trends)} multi-reading tests):")
    for row in sorted(trends, key=lambda r: -r["body"]["readings"])[:6]:
        b = row["body"]
        pts = " -> ".join(f"{p['value']}" for p in b["series"])
        print(f"      {ARROW[b['direction']]} {b['test'][:34]:<34} "
              f"{pts}  {b['unit']} (delta {b['delta']})")
    print()

t0 = time.time()
proposed = propose_claims(context)
print(f"[2] model proposed {len(proposed)} claims in {time.time() - t0:.2f}s "
      f"({settings.llm_model})\n")

memory = PatientMemory(PATIENT)
checks = resolve_all(memory, proposed)
decisions = evaluate_all(memory, checks, CLINICIAN.role)

for check, decision in zip(checks, decisions, strict=True):
    print(f"[{MARK[decision.result]}] {check.claim_text}")
    if decision.result is GateResult.BLOCK:
        print(f"          {decision.reason}")
    else:
        cited = f"{check.source_kind}/{check.source_name}"
        status = f" [{check.fact_status}]" if check.fact_status else ""
        print(f"          cites {cited}{status}"
              f"{', ' + str(len(check.source_events)) + ' events' if check.source_events else ''}")
        if decision.triggered_rules:
            print(f"          FLAGGED: {', '.join(decision.triggered_rules)}")
    print()

counts = summarise(decisions)
print(f"[3] gate verdict: {counts}")

for check, decision in zip(checks, decisions, strict=True):
    if decision.result is not GateResult.BLOCK:
        assert check.supported, "a claim was presented without evidence"
print("=== SESSION 2 OK -- nothing reached a clinician unverified ===")
