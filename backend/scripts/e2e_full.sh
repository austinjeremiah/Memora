#!/usr/bin/env bash
# MEMORA cumulative end-to-end.
#
# Runs the ENTIRE stack, every stage as a SEPARATE OS PROCESS, against real
# dependencies: real Synthea FHIR, a real Sibyl store, real Groq, real Base
# Sepolia. Nothing is mocked and nothing is simulated.
#
# The point is cumulative coverage: adding a stage never replaces the earlier
# ones, so a regression anywhere in phases 1..N fails this script.
#
# Every stage asserts BOTH a zero exit code AND an expected marker in the
# output. An earlier version checked `$?` after a pipe, which read tail's exit
# status rather than Python's and reported a false pass on a stage that had
# actually found nothing -- a green tick on broken behaviour is worse than a
# red one, so both conditions are now required.
#
#   usage: scripts/e2e_full.sh [FHIR_DIR]
set -uo pipefail

BACKEND="$(cd "$(dirname "$0")/.." && pwd)"
PY="$BACKEND/.venv/bin/python"
FHIR="${1:-$BACKEND/../vendor/synthea/output/fhir}"
TMP="$(mktemp -d)"
STORE="$TMP/memory.db"
# SIBYL_DB_PATH is the real setting name, so it is honoured by every entry
# point including inline -c calls. MEMORA_DB is kept for the demo scripts.
export MEMORA_DB="$STORE" SIBYL_DB_PATH="$STORE"

# HOME is redirected because Sibyl's free-tier cap is per ACCOUNT, not per
# store: sibyl_memory_client.aggregate_db_size() sums this run's store WITH
# ~/.sibyl-memory/memory.db and the Hermes profile stores. Without this the
# script competed for one 5 MB budget against the developer's demo store and
# died in stage 1 with CapExceededError -- measured at 5,246,976 bytes against
# a 5,242,880 cap, over by 4 KB, with every later stage failing for want of
# ingested data. A test whose result depends on unrelated state elsewhere on
# the machine is not a test, so this run gets a home of its own.
export HOME="$TMP/home"
mkdir -p "$HOME"
cd "$BACKEND"

PASS=0; FAIL=0
stage () {
  echo; echo "══════════════════════════════════════════════════════════════"
  echo "  $1"; echo "══════════════════════════════════════════════════════════════"
}
check () {
  if [ $? -eq 0 ]; then echo "  ✓ $1"; PASS=$((PASS+1));
  else echo "  ✗ $1"; FAIL=$((FAIL+1)); fi
}
# run <label> <expected-marker> <tail-lines> -- <command...>
run () {
  local label="$1" marker="$2" lines="$3"; shift 4
  local out rc
  out="$("$@" 2>&1)"; rc=$?
  echo "$out" | tail -n "$lines"
  if [ $rc -eq 0 ] && echo "$out" | grep -q -- "$marker"; then
    echo "  ✓ $label"; PASS=$((PASS+1))
  else
    echo "  ✗ $label   (exit=$rc, marker '$marker' $(echo "$out" | grep -qc -- "$marker" && echo found || echo missing))"
    FAIL=$((FAIL+1))
  fi
}

echo "MEMORA cumulative end-to-end"
echo "store: $STORE"

stage "STAGE 1/9 · Synthea ingestion into Sibyl  (phases 6-8)"
run "3 real Synthea patients ingested" "final:" 5 -- \
  "$PY" scripts/ingest_demo.py "$FHIR" 3

PATIENT="$("$PY" -c 'from memora.sibyl.client import known_patient_ids; print(known_patient_ids()[0])')"
if [ -z "$PATIENT" ]; then echo "FATAL: no patient discovered"; exit 1; fi
echo "  demo patient: $PATIENT"

stage "STAGE 2/9 · HTTP: patient discovery + raw memory view  (v2.1)"
API_PORT=8077
"$BACKEND/.venv/bin/uvicorn" memora.main:app --host 127.0.0.1 --port $API_PORT \
  --log-level warning >/dev/null 2>&1 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT
curl -s --retry-connrefused --retry 30 --retry-delay 1 -o /dev/null \
  "http://127.0.0.1:$API_PORT/health"

DISCOVERED=$(curl -s "http://127.0.0.1:$API_PORT/patients" \
  | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["patient_id"] if d else "")')
echo "  discovered from the store (nothing hardcoded): $DISCOVERED"
curl -s "http://127.0.0.1:$API_PORT/patients" | "$PY" -c '
import json,sys
for p in json.load(sys.stdin):
    print(f"    {p["patient_id"][:8]}…  {p["fact_count"]:>3} facts  {p["event_count"]:>3} events  "
          f"v{p["memory_version"]}  drug_allergy={p["has_drug_allergy"]}")'
[ -n "$DISCOVERED" ] && [ "$DISCOVERED" = "$PATIENT" ]
check "GET /patients discovered the real ingested patient"

curl -s "http://127.0.0.1:$API_PORT/patients/$PATIENT/memory" | "$PY" -c '
import json,sys
d=json.load(sys.stdin)
print(f"    {d["fact_count"]} facts, {d["event_count"]} events, memory_version={d["memory_version"]}")
print(f"    kinds: {sorted(d["facts"])}")
t=[x for x in d["trends"] if (x["readings"] or 0)>=3][:3]
for x in t:
    pts=" -> ".join(str(p["value"]) for p in x["series"])
    print(f"    {x["direction"]:<8} {x["test"][:30]:<30} {pts} {x["unit"]}")
assert d["fact_count"]>0 and d["trends"], "raw memory view returned nothing"'
check "GET /patients/{id}/memory exposed the raw record with trajectories"

kill $API_PID 2>/dev/null; trap - EXIT

stage "STAGE 3/9 · Cold-start situational recall  (phases 4-5, 9)"
run "fresh process recalled state; per-situation subsets differ" \
    "situational recall across a process boundary" 26 -- \
  "$PY" scripts/session_situations.py "$PATIENT"

stage "STAGE 4/9 · LLM proposal -> evidence -> gate  (phases 10-13)"
run "model proposed; every claim verified against memory" \
    "nothing reached a clinician unverified" 30 -- \
  "$PY" scripts/session_brief.py "$PATIENT" dr_arun

stage "STAGE 5/9 · Role-dependent authority on identical evidence  (phase 11)"
run "same evidence judged differently by role" \
    "role-dependent verdicts" 12 -- \
  "$PY" scripts/session_gate.py "$PATIENT"

stage "STAGE 6/9 · SENTINEL: proactive drift detection, no LLM  (v2)"
run "drift detected and announced as NEW" "NEW      " 22 -- \
  "$PY" scripts/session_sentinel.py icu_to_ward --seed-drift "$PATIENT"
echo
echo "  --- second sweep: the same finding must NOT re-announce ---"
run "finding tracked as PERSISTING, not re-alerted" "PERSISTING" 8 -- \
  "$PY" scripts/session_sentinel.py icu_to_ward

stage "STAGE 7/9 · Clinician approval anchored on Base Sepolia  (phase 15)"
run "approved state hashed, committed onchain, read back" \
    "anchored and verified onchain" 12 -- \
  "$PY" scripts/session_approve.py "$PATIENT" dr_maya

stage "STAGE 8/9 · EIP-712 clinician attestation on Base  (v2)"
run "state signed by a synthetic demo clinician key, recorded onchain" \
    "signed state recorded and verified onchain" 16 -- \
  "$PY" scripts/session_attest.py "$PATIENT" dr_maya

stage "STAGE 9/9 · THE GATE CRITERION: delete memory, must refuse"
rm -f "$STORE"*
OUT="$("$PY" scripts/session_brief.py "$PATIENT" dr_arun 2>&1)"; RC=$?
echo "$OUT" | tail -1
if [ $RC -ne 0 ] && echo "$OUT" | grep -q "SibylUnavailableError"; then
  echo "  ✓ MEMORA refused to answer without its memory layer"; PASS=$((PASS+1))
else
  echo "  ✗ MEMORA did NOT refuse (exit=$RC)"; FAIL=$((FAIL+1))
fi
if [ ! -f "$STORE" ]; then
  echo "  ✓ the store was NOT silently recreated"; PASS=$((PASS+1))
else
  echo "  ✗ the store was silently recreated"; FAIL=$((FAIL+1))
fi

echo; echo "══════════════════════════════════════════════════════════════"
echo "  CUMULATIVE E2E: $PASS passed, $FAIL failed"
echo "══════════════════════════════════════════════════════════════"
rm -rf "$TMP"
[ "$FAIL" -eq 0 ]
