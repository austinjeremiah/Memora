"""SESSION 2 -- a genuinely new OS process. Recalls what Session 1 wrote.

Shares no Python state with the writer: the only thing connecting them is
memory.db on disk. Usage: MEMORA_DB=/path/to/memory.db python scripts/session_recall.py
"""

import os
import sys
import time
from pathlib import Path

from memora.config import settings

if os.environ.get("MEMORA_DB"):
    settings.sibyl_db_path = Path(os.environ["MEMORA_DB"])

from memora.ontology.events import ClinicalEvent
from memora.ontology.kinds import (
    KIND_MEDICATION,
    STATUS_CONTRAINDICATED,
)
from memora.sibyl.client import PatientMemory

PATIENT = sys.argv[1] if len(sys.argv) > 1 else "P-10482"

print(f"=== SESSION 2 @ {time.strftime('%Y-%m-%d %H:%M:%S')} · pid {os.getpid()} ===")
print("    no prior conversation, no shared state -- fresh process")

m = PatientMemory(PATIENT, require_data=True)

flagged = m.list_facts(KIND_MEDICATION, status=STATUS_CONTRAINDICATED)
print(f"    contraindicated medications: {[r['name'] for r in flagged]}")
for row in flagged:
    print(f"      - {row['name']}: {row['body']['reason']}")

print("    history recalled from a process that no longer exists:")
for record in sorted(m.read_history(), key=lambda r: r["ts"]):
    e = ClinicalEvent.from_record(record)
    sev = f" [{e.severity}]" if e.severity else ""
    print(f"      {e.timestamp}  {e.event_type}{sev}: {e.summary}")

assert flagged, "SESSION 2 recalled nothing -- persistence is broken"
print("=== SESSION 2 OK -- state survived the process boundary ===")
