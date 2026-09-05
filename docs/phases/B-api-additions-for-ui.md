# Phase B — Backend API additions for the UI

**Status:** done · 4 commits (`eaf793f`, `f55ba84`, `c9537d2`, `1651d4f`)

Backend work done *before* frontend wiring began, so the UI would never need
to invent data the API could not give it.

---

## Why this phase existed

A frontend audit found the API was missing three things the UI genuinely
needed, and the frontend had already worked around two of them badly:

- `lib/config/demo-data.ts` shipped a **hardcoded patient id** (`P-10482`)
  with a comment admitting it was unverified. Real ids are Synthea UUIDs
  generated per ingestion run — they cannot be known ahead of time.
- `StatusStrip` hardcoded a **2 MiB quota cap**. The real cap is 5,242,880.
- Nothing exposed the **raw stored record**, so "persistent memory" could be
  claimed but not shown.

---

## What shipped

### B5 · `scripts/run_api.sh` — port 8000

The port was undocumented: no `uvicorn.run()`, no run script, and three
different ports had been used across tests and docs. 8000 now matches the
frontend's existing `DEFAULT_API_BASE_URL`.

### B1 · `GET /patients`

Returns every patient actually in the store, with enough to choose from:

```json
{ "patient_id": "0c33684a-…", "fact_count": 97, "event_count": 253,
  "memory_version": 253, "kinds": {...}, "has_drug_allergy": true,
  "last_updated": "…" }
```

Backed by `patient_summary()` in `memora/sibyl/client.py`. The reserved
Sentinel pseudo-tenant is excluded — it holds the digest, not clinical data.

### B2 · `GET /patients/{id}/memory`

The raw record: every WARM fact by kind, every lab trajectory **with its full
series**, and the COLD journal. `event_limit` defaults to 200.

Deliberately distinct from `GET /patients/{id}/context`, which returns one
situation's *ranked and capped* retrieval plan. `test_memory_view_is_unfiltered_unlike_context`
pins that difference — it is the whole reason the endpoint exists.

Trajectories are ranked ahead of single readings, because a five-point series
says something a lone value cannot.

### B3 + B4 · Wallet-mode attestation (Option B)

Two-step flow — the server derives the state hash (which requires re-verifying
every claim against live Sibyl state, so a browser cannot be trusted with it),
and the wallet signs only what memory has already justified:

```
POST /handoff/{id}/attestation-payload   → EIP-712 typed data + nonce
        wallet signs
POST /handoff/{id}/attest                → { signature, signer, issued_at, expires_at, nonce }
```

**Option B authorisation.** `CLINICIAN_WALLETS=dr_maya:0xABC,…` maps personas
to addresses. The load-bearing check is `may_sign_as(address, clinician_id)` —
being merely *authorised* is not enough. A wallet registered to Dr. Arun would
produce a cryptographically valid signature attributed to Dr. Maya; that is
refused with a 403.

No wallet configured → falls back to the clinician's synthetic demo key, so
the system works with nothing set up.

**The contract needed no changes.** `attest(a, signer, signature)` already
recovers and compares against the claimed signer.

---

## Bugs found and fixed

**Two tests failed because the contract was working correctly.** The state
hash is a digest of approved *content*, so identical approvals produce
identical hashes by design — and the contract refuses to re-attest one.

- `session_attest.py` now reports the existing attestation instead of erroring,
  keeping the e2e repeatable **without** weakening the contract or making the
  hash artificially unique.
- The `/approve` test adds a unique marker fact per run, as `/attest` already did.

Worth being explicit: these were not regressions. Loosening the contract to
make a test pass would have been the wrong fix.

---

## Verified

```
278 Python tests passed (Sibyl + Synthea + Groq + Base Sepolia)
255 offline-only (no API key, no network)
  5 compliance (the gate criterion)
 18 Solidity (Foundry)
cumulative e2e: 12 passed, 0 failed — and idempotent on repeat runs
```

New e2e **stage 2** starts a real uvicorn and asserts over HTTP that
`GET /patients` discovers the ingested patient and `GET /patients/{id}/memory`
returns trajectories. Nothing hardcoded survives that check.

---

## API surface after this phase — 14 routes

```
GET  /health                                 GET  /patients
GET  /readyz                                 GET  /patients/{id}/memory
GET  /clinicians                             GET  /patients/{id}/context
POST /handoff                                POST /handoff/{id}/approve
POST /handoff/{id}/attestation-payload       POST /handoff/{id}/attest
GET  /attestation/{state_hash}/verify        GET  /commitment/{hash}/verify
POST /sentinel/run                           GET  /sentinel/since-last-review
```

---

## Still open

- **LICENSE** — MIT or Apache-2.0. Blocks submission; needs a decision.
- **README** — a gate requirement (*"a judge can find where memory is written
  and read in under two minutes"*). Best written after the API settles.
