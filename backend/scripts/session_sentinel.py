"""SESSION -- fresh process. Sentinel: the proactive path, no model involved.

Sweeps ingested patients for memory drift -- a current WARM fact contradicting
its own COLD journal -- and reconciles findings against Sentinel's own digest,
so a finding is announced once and then tracked rather than re-alerted.

Run it twice in a row and the same finding reports NEW, then PERSISTING. That
is the anti-alert-fatigue property, demonstrated rather than described.

Usage: MEMORA_DB=... python scripts/session_sentinel.py [SITUATION] [--seed-drift PATIENT]
"""

import os
import sys
import time
from pathlib import Path

from memora.config import settings

if os.environ.get("MEMORA_DB"):
    settings.sibyl_db_path = Path(os.environ["MEMORA_DB"])

from memora.context.situations import Situation
from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    SEVERITY_CRITICAL,
    ClinicalEvent,
)
from memora.ontology.kinds import KIND_MEDICATION, STATUS_ACTIVE
from memora.sentinel.digest import load_digest
from memora.sentinel.runner import sweep
from memora.sibyl.client import PatientMemory, known_patient_ids

args = [a for a in sys.argv[1:] if not a.startswith("--")]
SITUATION = Situation(args[0]) if args else Situation.ICU_TO_WARD

print(f"=== SENTINEL SWEEP @ {time.strftime('%Y-%m-%d %H:%M:%S')} · pid {os.getpid()} ===")
print(f"    situation: {SITUATION.value} · fresh process, digest read from disk\n")

# Optionally plant a real contradiction so the sweep has something to find.
# Synthea never prescribes a drug a patient is allergic to, so genuine drift
# does not occur naturally in the source data -- it has to be introduced to be
# demonstrated. Stated plainly rather than passed off as discovered.
if "--seed-drift" in sys.argv:
    target = sys.argv[sys.argv.index("--seed-drift") + 1]
    m = PatientMemory(target)
    m.set_fact(KIND_MEDICATION, "lisinopril", {"label": "Lisinopril 10mg"},
               status=STATUS_ACTIVE)
    m.log_event(ClinicalEvent(EVENT_ADVERSE_REACTION,
                              "Documented adverse reaction to Lisinopril",
                              "2026-02-01T09:00:00Z", KIND_MEDICATION,
                              "lisinopril", "seeded-drift-1", SEVERITY_CRITICAL))
    print(f"    [seeded] planted a contradiction on {target[:8]}…: "
          f"lisinopril ACTIVE + documented adverse reaction\n")

patients = known_patient_ids()
print(f"    {len(patients)} patients discovered in the store")

prior = load_digest(SITUATION.value)
print(f"    digest holds {len(prior)} findings from previous runs\n")

run = sweep(SITUATION, patients)

print(f"[1] scanned {run.patients_scanned} patients, {run.records_checked} records")
print(f"[2] verdict: {run.by_status()}\n")

for finding in run.findings:
    mark = {"NEW": "NEW      ", "PERSISTING": "PERSISTING",
            "RESOLVED": "RESOLVED ", "ESCALATED": "ESCALATED"}[finding.status]
    print(f"  [{mark}] {finding.patient_id[:8]}…  {finding.kind}/{finding.name}")
    print(f"              {finding.reason[:88]}")
    if finding.triggered_rules:
        print(f"              rules: {', '.join(finding.triggered_rules)}")
    print(f"              seen {finding.runs_seen}x since {finding.first_seen_at[:19]}"
          f" · evidence: {finding.evidence_event}")
    print()

announce = run.announceable()
print(f"[3] {len(announce)} of {len(run.findings)} findings warrant announcing now")
print("    (PERSISTING findings stay tracked but do NOT re-alert)")
print("\n=== SENTINEL OK -- no model was called anywhere in this path ===")
