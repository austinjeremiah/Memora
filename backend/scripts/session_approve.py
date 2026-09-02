"""SESSION 2 -- fresh process. The complete MEMORA flow, ending on Base.

  Sibyl recall -> LLM proposal -> evidence -> gate -> clinician approval
  -> SHA-256 of the approved state -> Base Sepolia -> read back onchain

Only a hash leaves the machine. No patient data goes onchain, ever.

Usage: MEMORA_DB=/path/to/memory.db python scripts/session_approve.py [PATIENT] [CLINICIAN]
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
from memora.integrity.base_client import commit_hash, verify_hash
from memora.integrity.commitment import (
    canonical_commitment_payload,
    canonical_json,
    commitment_label,
    compute_commitment_hash,
)
from memora.llm.propose import propose_claims
from memora.sibyl.client import PatientMemory

PATIENT = sys.argv[1] if len(sys.argv) > 1 else "P-10482"
CLINICIAN = get_clinician(sys.argv[2] if len(sys.argv) > 2 else "dr_maya")

print(f"=== SESSION 2 @ {time.strftime('%Y-%m-%d %H:%M:%S')} · pid {os.getpid()} ===")
print(f"    {CLINICIAN.name} ({CLINICIAN.role.value}) · fresh process\n")

context = execute_plan(compile_plan(PATIENT, Situation.ICU_TO_WARD, CLINICIAN.role))
print(f"[1] recalled {context.fact_count()} facts, {len(context.history)} events")

proposed = propose_claims(context)
memory = PatientMemory(PATIENT)
checks = resolve_all(memory, proposed)
decisions = evaluate_all(memory, checks, CLINICIAN.role)
print(f"[2] {len(proposed)} proposed -> gate {summarise(decisions)}")

approved = [
    {"text": check.claim_text, "gate_result": decision.result.value}
    for check, decision in zip(checks, decisions, strict=True)
    if decision.result is not GateResult.BLOCK
]
print(f"[3] {CLINICIAN.name} approves {len(approved)} claims "
      f"(approval authority: {CLINICIAN.can_approve_handoff})")

payload = canonical_commitment_payload(PATIENT, "icu_to_ward", approved)
digest = compute_commitment_hash(payload)
blob = canonical_json(payload)
print(f"\n[4] canonical payload ({len(blob)} bytes) -> SHA-256")
print(f"    hash: 0x{digest.hex()}")
print(f"    label onchain: {commitment_label(PATIENT, 'icu_to_ward')}")
print("    NOTE: only the hash and label go onchain -- no claim text, no clinical detail")

print("\n[5] committing to Base Sepolia...")
receipt = commit_hash(digest, commitment_label(PATIENT, "icu_to_ward"))
print(f"    tx:       {receipt['tx_hash']}")
print(f"    block:    {receipt['block_number']}  gas: {receipt['gas_used']}")
print(f"    basescan: {receipt['basescan_url']}")

print("\n[6] reading it back from the chain...")
confirmed = verify_hash(digest)
print(f"    exists={confirmed['exists']} timestamp={confirmed['timestamp']} "
      f"committer={confirmed['committer']}")

assert confirmed["exists"], "commitment did not read back"
print("\n=== SESSION 2 OK -- approved state anchored and verified onchain ===")
