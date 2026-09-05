"""SESSION -- fresh process. Clinician-signed attestation recorded on Base.

The evolution of session_approve.py: that anchors an anonymous hash of an
approved state. This records WHO approved it, over WHAT evidence, in WHICH
clinical context, at WHICH point in the patient's memory -- as an EIP-712
signature the contract verifies, with replay protection it enforces.

No model is called here. Claims are read straight from verified memory, which
keeps the demo off Groq's per-minute token budget and makes the point that
attestation depends on memory, not on inference.

THE SIGNING KEYS ARE SYNTHETIC DEMO KEYS held server-side. They are not real
clinician identities and not an authentication mechanism.

Usage: MEMORA_DB=... python scripts/session_attest.py [PATIENT] [CLINICIAN]
"""

import os
import sys
import time
from pathlib import Path

from memora.config import settings

if os.environ.get("MEMORA_DB"):
    settings.sibyl_db_path = Path(os.environ["MEMORA_DB"])

from memora.attestation.chain import next_nonce, submit_attestation, verify_onchain
from memora.attestation.keys import synthetic_address
from memora.attestation.sign import sign_attestation
from memora.clinicians.roles import get_clinician
from memora.context.situations import Situation
from memora.evidence.resolver import resolve_claim
from memora.gate.gate import GateResult, evaluate_claim
from memora.integrity.commitment import (
    canonical_commitment_payload,
    compute_commitment_hash,
    compute_context_hash,
    compute_evidence_root,
)
from memora.integrity.errors import CommitmentExistsError
from memora.ontology.kinds import KIND_ALLERGY, KIND_MEDICATION
from memora.sibyl.client import PatientMemory

PATIENT = sys.argv[1] if len(sys.argv) > 1 else "P-10482"
CLINICIAN = get_clinician(sys.argv[2] if len(sys.argv) > 2 else "dr_maya")
SITUATION = Situation.ICU_TO_WARD

print(f"=== ATTESTATION @ {time.strftime('%Y-%m-%d %H:%M:%S')} · pid {os.getpid()} ===")
print(f"    {CLINICIAN.name} ({CLINICIAN.role.value}) · fresh process\n")

memory = PatientMemory(PATIENT, require_data=True)

# Build claims from verified memory -- no model in this path.
candidates = []
for kind in (KIND_MEDICATION, KIND_ALLERGY):
    for row in memory.list_facts(kind)[:3]:
        candidates.append((f"{row['name']} is recorded as {row['status']}",
                           kind, row["name"]))

verified, evidence_ids = [], []
for text, kind, name in candidates:
    check = resolve_claim(memory, text, kind, name)
    decision = evaluate_claim(memory, check, CLINICIAN.role)
    if decision.result is GateResult.BLOCK:
        continue
    verified.append({"text": text, "gate_result": decision.result.value})
    evidence_ids.extend(e.source_id for e in check.source_events if e.source_id)

print(f"[1] {len(verified)} claims re-verified against live memory")
print(f"[2] memory version: {memory.memory_version()} "
      f"(monotonic counter of everything recorded for this patient)")

state_hash = compute_commitment_hash(
    canonical_commitment_payload(PATIENT, SITUATION.value, verified))
evidence_root = compute_evidence_root(evidence_ids)
context_hash = compute_context_hash(SITUATION.value, CLINICIAN.role.value)

print("\n[3] what gets signed (all hashes, no clinical content):")
print(f"    stateHash     0x{state_hash.hex()}")
print(f"    evidenceRoot  0x{evidence_root.hex()}   ({len(set(evidence_ids))} source events)")
print(f"    contextHash   0x{context_hash.hex()}")

signer = synthetic_address(CLINICIAN.id)
nonce = next_nonce(signer)
print(f"\n[4] signing as {CLINICIAN.name}")
print(f"    signer  {signer}  (SYNTHETIC DEMO KEY -- not a real identity)")
print(f"    nonce   {nonce}   (read from the contract; replay protection)")

attestation = sign_attestation(
    clinician_id=CLINICIAN.id, state_hash=state_hash,
    evidence_root=evidence_root, context_hash=context_hash,
    memory_version=memory.memory_version(), nonce=nonce)
print(f"    digest  {attestation.digest}")
print(f"    expires in {attestation.expires_at - attestation.issued_at}s")

print("\n[5] submitting to Base Sepolia -- the CONTRACT verifies the signature")

# The state hash is a digest of the APPROVED CONTENT, so approving the same
# claims for the same patient and situation twice produces the same hash by
# design. The contract refuses to re-attest it, which is the replay protection
# doing its job rather than an error -- so re-running this script reports the
# existing attestation instead of failing. That keeps the demo repeatable
# without weakening the contract or making the hash artificially unique.
try:
    receipt = submit_attestation(attestation)
    print(f"    tx:       {receipt['tx_hash']}")
    print(f"    block:    {receipt['block_number']}  gas: {receipt['gas_used']}")
    print(f"    relayer:  {receipt['relayer']}  (pays gas, did NOT sign)")
    print(f"    basescan: {receipt['basescan_url']}")
except CommitmentExistsError:
    print("    REPLAY REFUSED by the contract -- this exact approved state was")
    print("    already attested. The first attestation stands unchanged.")

print("\n[6] reading it back from the chain...")
confirmed = verify_onchain(state_hash)
print(f"    exists={confirmed['exists']} signer={confirmed['signer']} "
      f"memory_version={confirmed['memory_version']}")

assert confirmed["exists"], "attestation did not read back"
assert confirmed["signer"] == signer, "recovered signer does not match"
print("\n=== ATTESTATION OK -- signed state recorded and verified onchain ===")
