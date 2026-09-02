"""Ingest real Synthea story patients into Sibyl.

Prints the store size after every patient, because the free-tier cap is
5,242,880 bytes and discovering the ceiling mid-demo is not an option.

Usage: MEMORA_DB=/path/to/memory.db python scripts/ingest_demo.py [FHIR_DIR] [N]
"""

import os
import sys
from pathlib import Path

from memora.config import settings

if os.environ.get("MEMORA_DB"):
    settings.sibyl_db_path = Path(os.environ["MEMORA_DB"])

from sibyl_memory_client import MemoryClient

from memora.ingest.pipeline import find_story_patients, ingest_patient

FHIR_DIR = Path(sys.argv[1] if len(sys.argv) > 1
                else "../vendor/synthea/output/fhir")
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 4

MemoryClient.local(str(settings.sibyl_db_path))
print(f"store: {settings.sibyl_db_path}")

candidates = find_story_patients(FHIR_DIR)[:LIMIT]
print(f"selected {len(candidates)} story patients with real drug allergies\n")

for candidate in candidates:
    name = Path(candidate["path"]).name.split("_")[0]
    report = ingest_patient(Path(candidate["path"]))
    print(f"{name:<12} {report.patient_id[:8]}…  "
          f"parsed={report.events_parsed:>4} written={report.events_written:>4}  "
          f"new={report.facts_new:>3} conf={report.facts_confirmed:>3} "
          f"chg={report.facts_changed:>3}")
    print(f"{'':<12} allergies={candidate['drug_allergies']}")
    print(f"{'':<12} kinds={report.kinds}")
    print(f"{'':<12} STORE {report.db_size_bytes:,} bytes "
          f"({report.pct_of_cap:.2f}% of the 5 MB cap)\n")

print(f"final: {report.db_size_bytes:,} / 5,242,880 bytes "
      f"({report.pct_of_cap:.2f}%)")
