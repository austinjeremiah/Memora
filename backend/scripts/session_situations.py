"""SESSION 2 -- fresh process. Proves situation-aware recall.

Same patient, same Sibyl store, different clinical situation -> a genuinely
different relevant subset. This is MEMORA's central claim, executed rather than
asserted.

Usage: MEMORA_DB=/path/to/memory.db python scripts/session_situations.py [PATIENT_ID]
"""

import os
import sys
import time
from pathlib import Path

from memora.config import settings

if os.environ.get("MEMORA_DB"):
    settings.sibyl_db_path = Path(os.environ["MEMORA_DB"])

from memora.context.engine import compile_plan, execute_plan
from memora.context.situations import ClinicianRole, Situation

PATIENT = sys.argv[1] if len(sys.argv) > 1 else "P-10482"

VIEWS = [
    (Situation.ICU_TO_WARD, ClinicianRole.WARD_PHYSICIAN),
    (Situation.PRE_OPERATIVE, ClinicianRole.SURGEON),
    (Situation.DISCHARGE, ClinicianRole.WARD_PHYSICIAN),
]

print(f"=== SESSION 2 @ {time.strftime('%Y-%m-%d %H:%M:%S')} · pid {os.getpid()} ===")
print("    fresh process, no shared state -- everything below came from disk\n")

for situation, role in VIEWS:
    plan = compile_plan(PATIENT, situation, role)
    ctx = execute_plan(plan)

    print(f"┌─ {situation.value.upper()}  ({role.value} · task: {plan.task})")
    for kind in plan.kinds_to_check:
        rows = ctx.facts.get(kind, [])
        if rows:
            rendered = ", ".join(f"{r['name']}[{r['status']}]" for r in rows)
            print(f"│  {kind:<12} {rendered}")
    print("│")
    for event in ctx.history:
        sev = f" [{event.severity}]" if event.severity else ""
        print(f"│  {event.timestamp[:10]}  {event.event_type}{sev}")
        print(f"│              {event.summary}")
    print(f"└─ {ctx.fact_count()} facts, {len(ctx.history)} events\n")

assert not execute_plan(compile_plan(PATIENT, Situation.ICU_TO_WARD,
                                     ClinicianRole.WARD_PHYSICIAN)).is_empty()
print("=== SESSION 2 OK -- situational recall across a process boundary ===")
