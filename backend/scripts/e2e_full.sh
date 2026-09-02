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
cd "$BACKEND"

PASS=0; FAIL=0
stage () {
  echo; echo "══════════════════════════════════════════════════════════════"
  echo "  $1"; echo "══════════════════════════════════════════════════════════════"
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

stage "STAGE 1/7 · Synthea ingestion into Sibyl  (phases 6-8)"
run "3 real Synthea patients ingested" "final:" 5 -- \
  "$PY" scripts/ingest_demo.py "$FHIR" 3

PATIENT="$("$PY" -c 'from memora.sibyl.client import known_patient_ids; print(known_patient_ids()[0])')"
if [ -z "$PATIENT" ]; then echo "FATAL: no patient discovered"; exit 1; fi
echo "  demo patient: $PATIENT"

stage "STAGE 2/7 · Cold-start situational recall  (phases 4-5, 9)"
run "fresh process recalled state; per-situation subsets differ" \
    "situational recall across a process boundary" 26 -- \
  "$PY" scripts/session_situations.py "$PATIENT"

stage "STAGE 3/7 · LLM proposal -> evidence -> gate  (phases 10-13)"
run "model proposed; every claim verified against memory" \
    "nothing reached a clinician unverified" 30 -- \
  "$PY" scripts/session_brief.py "$PATIENT" dr_arun

stage "STAGE 4/7 · Role-dependent authority on identical evidence  (phase 11)"
run "same evidence judged differently by role" \
    "role-dependent verdicts" 12 -- \
  "$PY" scripts/session_gate.py "$PATIENT"

stage "STAGE 5/7 · SENTINEL: proactive drift detection, no LLM  (v2)"
run "drift detected and announced as NEW" "NEW      " 22 -- \
  "$PY" scripts/session_sentinel.py icu_to_ward --seed-drift "$PATIENT"
echo
echo "  --- second sweep: the same finding must NOT re-announce ---"
run "finding tracked as PERSISTING, not re-alerted" "PERSISTING" 8 -- \
  "$PY" scripts/session_sentinel.py icu_to_ward

stage "STAGE 6/7 · Clinician approval anchored on Base Sepolia  (phase 15)"
run "approved state hashed, committed onchain, read back" \
    "anchored and verified onchain" 12 -- \
  "$PY" scripts/session_approve.py "$PATIENT" dr_maya

stage "STAGE 7/7 · THE GATE CRITERION: delete memory, must refuse"
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
