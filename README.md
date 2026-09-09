# MEMORA

**Persistent clinical memory with a deterministic safety gate, built on Sibyl Memory.**

When a patient moves from intensive care to a ward, everything the previous team
learned has to be handed over. Roughly 80% of serious medical errors involve a
failure at that moment. An LLM summary makes it worse, not better: it produces
fluent prose nobody can verify.

MEMORA keeps a patient's clinical history in Sibyl Memory, lets an autonomous
agent watch that memory for contradictions, and puts every model-proposed claim
through a deterministic gate that checks it against a stored record before a
clinician ever reads it.

**The model proposes. It never decides.**

Synthetic patients only (Synthea). Not for clinical use.

---

## The eligibility gate, answered

> *Build an agent whose persistent memory changes what it knows, decides, or does across sessions.*

### 01 — Persist context that matters to the agent

Sentinel keeps a **digest** in Sibyl: every contradiction it has found, how many
runs it has seen each one, and its lifecycle state.

`backend/memora/sentinel/digest.py` → `save_digest()` / `load_digest()`

### 02 — Recall it in a genuinely fresh session

Every session records the **`BOOT_ID`** of the API process that opened it, generated
once per Python process at import.

A session carrying a *different* boot id than the running process was written by a
process that no longer exists — so Sibyl is the only path its work survived by.
This is checkable, not asserted:

```
this process     : 4eede932e3e1
prior sessions   : 6   (5 written by processes that no longer exist)
crossed_restart  : True
```

`backend/memora/sessions/runtime.py` · `backend/memora/sessions/recall.py`

### 03 — Use it to change a decision, action, or result

Same question, same patient, **different process**:

| "What medications is this patient on, and are any of them a problem?" | Verdict |
|---|---|
| Before the reaction was documented | `ALLOW` — *"the records do not indicate a problem"* |
| After, in a process that never saw it | **`NEEDS_REVIEW`** — chlorpheniramine flagged |

And the agent acts on its own. On the third run of a contradiction it crosses its
escalation threshold and **writes into the patient's record with no human request**:

```
[sentinel] recalled digest from previous runs: 2 tracked finding(s)
[sentinel]   CONTRADICTION  medication/chlorpheniramine_maleate_2_mg_ml_oral_solution
[sentinel]   read f5fe5e84: 67 records from persistent memory
[sentinel]   ESCALATED  medication/chlorpheniramine…  (seen 3x across runs)
[sentinel]   ACTING UNPROMPTED: threshold of 3 runs crossed,
             writing an escalation into f5fe5e84's record
[sentinel] digest saved to memory: 3 finding(s) carried to the next run
[sentinel] sweep done  checked=191  findings=3  actions=1
```

**That count of three only exists because Sibyl carried it between runs.**

### The deletion test

Delete `memory.db` and every clinical endpoint returns 503. It does not degrade
into an empty answer that looks like a result.

```bash
mv ~/.sibyl-memory/memory.db{,.bak}    # every clinical route now 503s
mv ~/.sibyl-memory/memory.db{.bak,}    # everything returns
```

Automated in `backend/tests/compliance/test_deletion.py`, and runnable from the
UI on the **Proof** page.

**Why that needed an explicit guard.** `MemoryClient.local()` **silently recreates**
an empty store when the file is missing — it does not raise. Without a check
*before* the client is constructed, MEMORA would have answered 200 from nothing
while every test stayed green. Found by running the SDK, not by reading its docs.

`backend/memora/sibyl/preflight.py`

---

## Where memory is written and read

Exactly one file imports `sibyl_memory_client`. Everything else goes through it.

**`backend/memora/sibyl/client.py`** — the single chokepoint.

| Tier | Method | Line | Holds |
|---|---|---|---|
| HOT | `set_context` / `get_context` | 81 / 85 | memory version counter |
| WARM | `set_fact` / `get_fact` | 90 / 97 | medications, allergies, diagnoses, procedures, lab trends, **sessions, threads** |
| WARM | `list_facts` | 114 | enumeration by kind and status |
| COLD | `log_event` | 122 | append-only clinical journal |
| COLD | `read_history` | 160 | the journal back out |
| — | `search` | 197 | FTS5 full-text retrieval |

**Writers:** `ingest/pipeline.py` (FHIR → tiers) · `sentinel/actions.py` (escalations) ·
`sessions/store.py` (sessions, threads, questions) · `api/routes.py` (clinical events)

**Readers:** `context/engine.py` (situational retrieval) · `evidence/resolver.py`
(claim → record) · `gate/gate.py` (policy) · `sentinel/drift.py` (contradiction detection) ·
`sessions/recall.py` (cross-session recall) · `llm/answer.py` (question-driven FTS5)

---

## Architecture

```
                          ┌──────────────────────────┐
   Synthea FHIR R4 ──────►│   ingest/pipeline.py     │
   60 bundles             │   parse · classify · fold│
   69,110 resources       └────────────┬─────────────┘
                                       │
                          ╔════════════▼═════════════════════════════╗
                          ║          SIBYL MEMORY                    ║
                          ║  HOT    state / memory version           ║
                          ║  WARM   facts · sessions · threads       ║
                          ║  COLD   append-only journal              ║
                          ║  REF    lookups     ARCHIVE  superseded  ║
                          ║  one SQLite store · FTS5 · per-patient   ║
                          ║  tenant · 5 MB free-tier cap             ║
                          ╚══╦═══════════════╦═══════════════════╦═══╝
                             │               │                   │
              ┌──────────────▼───┐  ┌────────▼────────┐  ┌───────▼────────┐
              │  CONTEXT ENGINE  │  │    SENTINEL     │  │    SESSIONS    │
              │  situation +     │  │   autonomous    │  │  boot_id per   │
              │  role → plan     │  │   NO LLM here   │  │  process       │
              └────────┬─────────┘  └────────┬────────┘  └───────┬────────┘
                       │                     │                   │
              ┌────────▼─────────┐           │ writes            │ recalls
              │   LLM PROPOSES   │           │ escalations       │ prior
              │   Groq · claims  │           │ back into ────────┘ sessions
              └────────┬─────────┘           │ memory
                       │                     │
              ┌────────▼─────────┐           │
              │ EVIDENCE RESOLVER│◄──────────┘
              │ claim → record?  │   unsourced claim = rejected
              └────────┬─────────┘
                       │
              ┌────────▼─────────┐
              │       GATE       │   deterministic. no model.
              │ ALLOW / REVIEW / │   role authority + policy rules
              │      BLOCK       │
              └────────┬─────────┘
                       │
              ┌────────▼─────────┐        ┌──────────────────────┐
              │  CLINICIAN UI    │───────►│  BASE SEPOLIA        │
              │  Next.js         │ EIP712 │  Attestation.sol     │
              └──────────────────┘        │  Commitment.sol      │
                                          │  digest only         │
                                          └──────────────────────┘
```

### The two agent loops

```
REACTIVE — a clinician documents an event
  POST /patients/{id}/events
        │ write to COLD journal
        ▼
  sweep() fires automatically, unprompted
        │ read WARM facts vs COLD journal
        ▼
  contradiction found → digest updated → carried forward


AUTONOMOUS — the escalation threshold
  run 1  NEW          seen once,  recorded in digest
  run 2  PERSISTING   seen twice, deliberately does NOT re-alert
  run 3  ESCALATED    threshold crossed
         └─► writes a critical event into the patient's record
             with no human request

  The run count is only possible because the digest persists.


COORDINATION — one agent's finding changes another's answer
  Sentinel writes  "flagged for review: conflicted history"
        │  (into Sibyl, as a critical journal event)
        ▼
  A later question retrieves it via FTS5
        ▼
  The gate reads the critical event and returns NEEDS_REVIEW
        instead of ALLOW
```

---

## Tech stack

### Memory — Sibyl (mandatory)

`sibyl-memory-client` **0.7.0**. Local-first SQLite + FTS5, five tiers, one tenant
per patient. Free tier caps at **5,242,880 bytes**, measured **per account across all
stores** — not per file.

**Current store: 3,661,824 bytes (69.8%) · 3 patients · 707 events · 285 facts**

### Backend — Python 3.14

| | |
|---|---|
| API | FastAPI 0.141 · Uvicorn 0.52 |
| Validation | Pydantic 2.13 |
| LLM | `openai` SDK → **Groq**, `openai/gpt-oss-120b` |
| Chain | web3.py 7.16 · eth-account 0.14 |
| Test | pytest 9.1 · ruff |

**55 modules · 23 routes · 318 tests**

```
api          1403   23 REST routes
ingest        722   FHIR R4 → memory tiers
sentinel      653   autonomous drift detection
sibyl         554   the single SDK chokepoint
attestation   539   EIP-712 sign / verify / anchor
llm           422   prompting, key pool, answer resolution
gate          303   deterministic policy rules
sessions      282   sessions, threads, cross-restart recall
integrity     266   state hashing
context       252   situation-driven retrieval
evidence      171   claim → record provenance
ontology      127   6 clinical entity kinds
clinicians     45   roles + authority table
```

### Data — Synthea

Synthetic FHIR R4, Apache-2.0. 60 bundles, 69,110 resources generated; 3 ingested.
Every patient ID is a UUID produced at ingestion — nothing is hardcoded.

### Chain — Base Sepolia (84532)

Foundry 1.5.1 · Solidity 0.8.24 · OpenZeppelin `EIP712` / `Nonces` / `ECDSA`

| Contract | Address |
|---|---|
| `Attestation.sol` | [`0xc54122E46DDbF4F88a8D23d32586DC1cB0d8888e`](https://sepolia.basescan.org/address/0xc54122E46DDbF4F88a8D23d32586DC1cB0d8888e) |
| `Commitment.sol` | [`0x8B289101a7d6Bd7d066526B7b8D899Df582dd6b5`](https://sepolia.basescan.org/address/0x8B289101a7d6Bd7d066526B7b8D899Df582dd6b5) |

A clinician signs the **state of memory** as EIP-712 typed data — nonce and deadline
for replay protection, and the contract verifies the signature onchain. Only a
one-way digest leaves the machine; no patient data is ever written to a chain.

### Frontend — Next.js 15.5 / React 19.1

wagmi 3.7 · viem 2.56 (injected connector, deliberately not RainbowKit) ·
TanStack Query · TypeScript 5

**60 files · 10 pages.** No UI framework and no chart library: the design system is
built on the landing page's own CSS variables, and every chart is hand-drawn SVG
over real API responses.

---

## Running it

```bash
# 1. synthetic patients (needs Java 21)
mkdir -p vendor/synthea && cd vendor/synthea
curl -L -o synthea-with-dependencies.jar \
  https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar
java -jar synthea-with-dependencies.jar -p 40 \
  --exporter.fhir.export true --exporter.baseDirectory ./output Massachusetts
cd ../..

# 2. backend
cd backend
python3 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
cp .env.example .env          # add LLM_API_KEY (Groq) and BASE_PRIVATE_KEY
./.venv/bin/python scripts/ingest_demo.py ../vendor/synthea/output/fhir 3
./scripts/run_api.sh          # :8000

# 3. frontend
cd frontend && npm install && npm run dev   # :3000 → /app
```

**Use 3 patients, not more.** Three sits at ~70% of Sibyl's free-tier cap; a fourth
risks `CapExceededError` mid-demo. The ingest script prints the size after each one.

Contract tests need submodules: `git clone --recursive`, or `git submodule update --init`.

### Tests

```bash
cd backend
./.venv/bin/python -m pytest -q                              # 318, needs keys
./.venv/bin/python -m pytest -q -m "not llm and not chain"   # offline subset
bash scripts/e2e_full.sh          # cumulative, each stage a separate OS process
cd contracts && forge test        # 18 Solidity
```

`scripts/e2e_full.sh` redirects `HOME`, because Sibyl's cap is per *account*: without
that, the test's temp store is summed with your demo store and stage 1 dies at
5,246,976 bytes against a 5,242,880 cap.

---

## Design decisions worth knowing

**No mocks, anywhere.** No mocking library is installed. This is not fastidiousness:
the original plan's *mocked* gate test returned `{"status": "contraindicated"}` as an
entire record and passed green, while the real SDK returns a row with the payload
under `body` and lifecycle in a `status` column. The real code read an unset column
and the policy rule **could never fire**. The mock encoded the assumption and hid
the bug.

**Eight SDK contract corrections found by running the dependency**, not reading its
docs: `get_entity` raises rather than returning `None`; entity getters return the row,
so payload is under `body` and lifecycle in the `status` column; `write_event` is
keyword-only; `read_events` truncates at 50; the free-tier cap is per account, not
per store; and `MemoryClient.local()` silently recreates a deleted store.

**Sentinel runs no model.** Drift detection compares WARM facts against the COLD
journal. Both sides come from the same store, so they cannot both be right — and a
contradiction cannot be hallucinated.

**PERSISTING deliberately does not re-alert.** A finding seen twice is tracked in the
digest and visible in the since-last-review view, but it does not fire again. Alarm
fatigue is a real clinical harm.

**Role authority is load-bearing, not cosmetic.** A surgeon sees allergies, procedures
and medications — no diagnoses, no lab trends — and cannot approve a handover. The
same table drives retrieval *and* the gate.

**A wallet cannot sign as a clinician it is not registered to.** A cryptographically
valid signature with the wrong attribution is refused.
`backend/memora/attestation/keys.py` → `may_sign_as()`

**The LLM key pool exists because of `/compare`.** It issues three handoffs in
parallel and Groq's free tier allows 8,000 tokens per minute, so one key 429s
mid-run. Keys rotate round-robin with failover. Groq meters per *account*, so extra
keys only help from separate accounts — the code says so rather than implying
otherwise.

---

## Partner stacks

**Base** — two contracts deployed on Base Sepolia and exercised in the demo: an
EIP-712 clinician signature verified onchain by `Attestation.sol`, and a state
commitment in `Commitment.sol`. Real transactions, viewable on Basescan.

**Virtuals Protocol** — **not exercised.** Registration was attempted and abandoned;
no ACP job was run and no agent was registered. Claiming it would be claiming a
stack a judge cannot see doing real work.

---

## Prior work declaration

All backend, contract and frontend code in this repository was written during the
build window (Sep 1–10, 2026). The landing page began as a Framer export and was
rewritten to consume live API data; its design tokens are reused throughout the
application so the two share one visual language.

Third-party dependencies are listed in `backend/pyproject.toml`,
`frontend/package.json` and `backend/contracts/lib/`. Synthea is Apache-2.0.
Sibyl Memory is the mandatory memory layer for this hackathon.

---

## Phase documentation

Every phase has a written record in [`docs/phases/`](docs/phases/) — what was built,
what broke, and what was decided against. Start with
[`docs/phases/README.md`](docs/phases/README.md); the fresh-session work is
[`F11`](docs/phases/F11-sessions-and-fresh-session-recall.md).

---

## Licence

MIT. See [LICENSE](LICENSE).

**Synthetic patient data only. Not a medical device. Not for clinical use.**
