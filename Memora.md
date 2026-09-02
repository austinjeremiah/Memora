# MEMORA — Backend Build Bible
## Persistent Clinical Memory + Deterministic Safety Gate, on Sibyl Memory + Base
### Sibyl Labs Hackathon · Build window Sep 1–10, 2026

> **Status:** implementation-ready. Every Sibyl Memory claim below is checked against `docs.sibyllabs.org` (memory overview, install, concepts, integrations) and `sibyllabs.org` itself, fetched today — not carried over from the earlier planning docs without re-verification. Every hackathon-rule claim is checked against `hack.sibyllabs.org/rules`, fetched today. Where something genuinely isn't documented, this doc says so explicitly and gives you a Phase 1 probe to resolve it empirically, instead of guessing.

---

# 0. Ground Truth — What Changed, What's Confirmed, What You Still Have To Verify Yourself

## 0.1 Confirmed, and now precise (not just "yes it's SQLite")

Straight from `docs.sibyllabs.org/memory/concepts` and `/integrations`:

- **Package split.** `sibyl-memory-cli` (CLI + MCP, for coding-agent use) vs. `sibyl-memory-client` (the raw Python SDK — this is what MEMORA's backend imports) vs. `sibyl-memory-mcp` (MCP server only) vs. `sibyl-memory-hermes` (Hermes Agent plugin). MEMORA needs exactly one of these at runtime: `sibyl-memory-client`. `sibyl-memory-cli` is still needed once, at setup time, to activate your account.
- **The real SDK surface** (five tiers, one method pair each):
  ```python
  from sibyl_memory_client import MemoryClient
  memory = MemoryClient.local("~/.sibyl-memory/memory.db")

  memory.set_state(key, body)          # HOT
  memory.get_state(key)
  memory.set_entity(kind, name, body)  # WARM — UNIQUE (tenant_id, category, name)
  memory.get_entity(kind, name)
  memory.write_event(acted=[...])      # COLD — append-only
  memory.read_events(...)
  memory.set_reference(key, body)      # REFERENCE
  memory.get_reference(key)
  memory.archive_entity(kind, name)    # ARCHIVE — recoverable
  memory.delete_entity(kind, name)     # hard delete — NOT recoverable
  memory.search_entities(query)        # FTS5 keyword search, NOT semantic
  ```
- **It is local-first.** *"Everything is local; nothing round-trips to a server."* Storage is a single SQLite file on disk (default `~/.sibyl-memory/memory.db`). This is a feature for the demo (a fresh process re-opening the same file is a completely legitimate "fresh session"), but it means MEMORA is a single-server, single-SQLite-file application for the hackathon build — not a distributed multi-region system, and the doc should not claim otherwise.
- **Multi-tenant by design, enforced at the schema level.** *"Every read and write is scoped by `tenant_id`... `UNIQUE (tenant_id, category, name)`."* This is the real mechanism behind patient isolation — see §0.3, because the exact way to *set* `tenant_id` from the SDK is not shown in any example we could find, and needs a Phase 1 probe.
- **Retrieval is FTS5 full-text search, never embeddings.** *"No vector index, no embedding model to host... the answer is found by structure and text."* `search_entities(query)` is keyword matching. This determines how MEMORA names things (§6) — naming has to be search-friendly, because that's literally what gets matched.
- **Forgetting vs. deleting is a real, separate distinction.** `archive_entity` is recoverable (moves to an archive table, stays on disk). `delete_entity` is a permanent hard delete. MEMORA never calls `delete_entity` on clinical data — ever. Use `archive_entity` for anything MEMORA needs to "retire."

## 0.2 New and load-bearing: the free-tier quota cap

Not mentioned in any planning doc so far, and it will silently break a demo if you don't plan around it. From the `sibyl-memory-cli` package's own documented `sibyl status` output:

```text
SERVER
  Tier         FREE
  Cap bytes    2,097,152        ← 2 MiB hard cap on the free tier
  $SIBYL held  0
  Threshold    100,000          ← $SIBYL stake needed to lift the cap
  Qualified    no
```

The free tier caps your local memory database at **2 MiB**. Lifting it requires either staking 100,000 $SIBYL (liquid + staked) on Base, or a paid subscription ($29/mo, $79/quarter, $290/yr, USDC). **This changes the scope of the synthetic-patient plan.** "Thousands of synthetic patients with full longitudinal ICU histories" from the earlier planning docs will not fit in 2 MiB — SQLite row overhead plus JSON entity bodies adds up fast. Plan for a **small, curated set of "story patients"** (realistically 3–8 patients with a genuinely deep history each, not a large flat population), and treat `sibyl status` as a build-time gauge you check after every ingestion run, not something to discover mid-demo. Phase 1 includes a probe script that prints DB size after every write batch specifically so this never surprises you.

If you blow past 2 MiB mid-build: either trim the synthetic dataset, or register a Base wallet and stake/subscribe — cheap relative to the $10,000 prize pool, and arguably worth doing anyway since `sibyl init` already asks you to sign in with a wallet, and you need a Base wallet for the integrity-commitment piece regardless (§15). Decide this in Phase 1, not Day 9.

## 0.3 Genuinely unconfirmed — resolve this in Phase 1, don't assume

**How to scope `tenant_id` per patient from the SDK.** Every code example in the official docs (`memory.set_entity("project", "atlas", {...})`) omits `tenant_id` entirely — it's not clear whether `MemoryClient.local(path)` binds one fixed tenant per local install (tied to your `sibyl init` account), or whether individual calls/a client constructor can pass a `tenant_id` override for true per-patient isolation within one file.

**Do not guess.** Phase 1's probe script (§4.4) tests both hypotheses directly — `inspect.signature(MemoryClient.local)` and `inspect.signature(memory.set_entity)` to see what the installed package actually accepts, then a live round-trip test. Two fallback designs, safe either way:

- **If per-call/per-client `tenant_id` is supported:** use one tenant per patient (`tenant_id="patient-P-10482"`) — cleanest, matches the docs' own stated design intent, gives you real DB-level isolation for free.
- **If it is not exposed at this SDK version:** fall back to a naming-convention scope inside one tenant — every `kind`/`name` is prefixed with the patient id (`kind="medication"`, `name="P-10482::drug_a"`). This is verified-compatible with the documented API regardless of the tenant_id answer, so it's the safe default MEMORA's repository layer (§8) implements first; the tenant-per-patient optimization is a Phase 1 upgrade *if* confirmed available, not a blocking dependency.

## 0.4 The gate rules, restated precisely (source: `hack.sibyllabs.org/rules`, fetched today)

These are pass/fail, not stylistic advice — every phase below is built to satisfy them by construction, not by hoping the demo goes well:

- **The litmus test:** *"delete the Sibyl Memory layer. Does the project still do what it claims? If yes, it is not load-bearing, and it is disqualified."* → Phase 17 includes an actual automated test that renames `memory.db` and asserts the app can no longer answer.
- **Cold-start recall in the demo video** must be *"one continuous unedited segment with an on-screen timestamp or commit hash."* → Phase 16 is dedicated entirely to the mechanics of proving this on camera.
- **Rubric: memory 40%, innovation 25%, technical execution 20%, pitch 15%.** *"Recall is competitive; coordination and dynamic-storage patterns top the band."* → this is why the Safety Gate (Phase 11) isn't optional scope, it's the difference between mid-band and top-band on 40% of your score.
- **Partner multiplier:** Base bonus needs *"an executed onchain action... shown in the demo"* — a contract interaction qualifies. Virtuals needs a **real, exercised** integration or it earns nothing — this doc does not include a Virtuals phase; add one only if you find a genuine use, per the earlier discussion.
- **Submission:** MIT or Apache-2.0 license (not open-ended), a README with a **Prior Work declaration**, two public posts (video + a build-log) tagging `@sibylcap` and any claimed partner.

## 0.5 Declared prior work (goes in your actual README verbatim, adjust as needed)

> *The deterministic evidence/policy/authority gate pattern in this project was conceptually inspired by Sibyl Labs' own publicly documented "Compliance" pillar (`sibyllabs.org`): "You declare the rules the agent must follow, and a deterministic gate enforces them between the model and every action. A rule-breaking action never runs. The model can be wrong. The gate can't." MEMORA implements this pattern independently, in Python, scoped to clinical-context claims rather than agent actions in general.*


---

# 1. Architecture Overview

```text
                    SYNTHEA (Java)
                          |
                          v
              Synthetic FHIR patient bundles
                          |
                          v
              Ingestion Pipeline (Phase 8)
              parse -> normalize -> change-detect
                          |
                          v
              Sibyl Repository Layer (Phase 5)
      +-------------------+-------------------+
      |                   |                   |
   HOT state          WARM entities       COLD journal
  (current context)  (current facts)    (what happened)
      +-------------------+-------------------+
                          |
                   SIBYL MEMORY (local SQLite + FTS5)
                          |
                 [ process terminates ]
                          |
                   [ fresh process starts ]
                          |
                          v
              Context Engine (Phase 9)
      situation + role + task -> retrieval plan
                          |
                          v
              Evidence Resolver (Phase 10)
        LLM proposal -> checked against Sibyl records
                          |
                          v
              Deterministic Safety Gate (Phase 11)
         evidence check + policy check + authority check
                          |
              +-----------+-----------+
              v                       v
           ALLOW                   BLOCK
              |                       |
              v                       v
       Clinician review      Refuse + show evidence
              |
              v
       Canonical approved state
              |
              v
       SHA-256 commitment
              |
              v
       Base (Phase 15) — contract interaction
```

**The one sentence:** MEMORA remembers a patient's history in Sibyl, and cannot let an LLM turn an unsupported or unauthorized claim into trusted clinical output — the gate checks every proposal against what's actually in persistent memory before it reaches the clinician.

**Non-negotiables, unchanged in spirit from the planning docs, restated as build constraints:**
1. The LLM proposes; it never has final authority. Every important claim passes through the Evidence Resolver and the Gate before it's shown as verified.
2. History is never deleted — `archive_entity`, never `delete_entity`, for any clinical data.
3. No code path answers confidently without a real Sibyl read. Verified explicitly by an automated deletion test (Phase 17).
4. Every claim is evidence-linked: source event ID, timestamp, entity reference. No exceptions.
5. Patient data never goes onchain. Only a hash of an approved, clinician-reviewed state.
6. Synthetic data only. This is stated plainly in the README, not just implied by using Synthea.

---

# 2. Repository Layout

```text
memora/
├── vendor/
│   └── synthea/                    # git clone, built with Gradle, gitignored
│
├── backend/
│   ├── memora/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app entrypoint
│   │   ├── config.py
│   │   │
│   │   ├── sibyl/
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # thin wrapper over MemoryClient, quota-aware
│   │   │   ├── keys.py             # patient-scoped naming convention (Phase 4)
│   │   │   └── errors.py
│   │   │
│   │   ├── ontology/
│   │   │   ├── __init__.py
│   │   │   ├── kinds.py            # every `kind` string MEMORA uses, one place
│   │   │   └── events.py           # event schema (acted=[...] structure)
│   │   │
│   │   ├── ingest/
│   │   │   ├── __init__.py
│   │   │   ├── synthea_parser.py   # FHIR bundle -> internal event objects
│   │   │   ├── change_detector.py  # new vs. confirmed vs. superseded
│   │   │   └── pipeline.py         # orchestrates parse -> write
│   │   │
│   │   ├── context/
│   │   │   ├── __init__.py
│   │   │   ├── situations.py       # ICU_TO_WARD / PRE_OP / DISCHARGE definitions
│   │   │   ├── engine.py           # situation + role + task -> retrieval plan
│   │   │   └── retrieve.py         # executes the plan against Sibyl
│   │   │
│   │   ├── evidence/
│   │   │   ├── __init__.py
│   │   │   └── resolver.py         # claim -> Sibyl record -> verified/rejected
│   │   │
│   │   ├── gate/
│   │   │   ├── __init__.py
│   │   │   ├── policy.py           # declared clinical policy rules
│   │   │   ├── authority.py        # clinician role/task permissions
│   │   │   └── gate.py             # the deterministic ALLOW/BLOCK function
│   │   │
│   │   ├── clinicians/
│   │   │   └── roles.py            # Dr. Maya / Dr. Arun personas
│   │   │
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # OpenAI-compatible client (Cerebras/Groq)
│   │   │   └── propose.py          # evidence -> proposed clinical brief
│   │   │
│   │   ├── integrity/
│   │   │   ├── __init__.py
│   │   │   ├── commitment.py       # canonical serialization + SHA-256
│   │   │   └── base_client.py      # web3.py contract interaction
│   │   │
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── routes.py
│   │       └── schemas.py          # pydantic request/response models
│   │
│   ├── scripts/
│   │   ├── verify_sibyl.py         # Phase 1 — run first, always
│   │   ├── generate_patients.py    # Synthea invocation + FHIR pull
│   │   ├── ingest_demo.py          # writes the story patients into Sibyl
│   │   ├── session1.py             # demo: writes history, then exits
│   │   ├── session2.py             # demo: genuinely fresh process, recalls
│   │   └── deletion_test.py        # automated gate-compliance check
│   │
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── compliance/             # the deletion test + quota test live here
│   │
│   ├── contracts/
│   │   └── Commitment.sol
│   │
│   ├── pyproject.toml
│   ├── .env.example
│   └── Dockerfile
│
└── README.md
```


---

# 3. Phase 0 — Environment & Prerequisites

Install, in order:

- **Python 3.11+** (3.12 recommended — `sibyl-memory-client` has no documented lower bound beyond "modern Python 3," pin to what's on your machine and confirm in Phase 1)
- **Java 21+ and Gradle** — Synthea is a Java project, builds with its own Gradle wrapper
- **Node.js 20+** — only needed if you add a frontend later; the backend itself is pure Python
- **`uv` or `pip` + `venv`** — this doc uses `uv` for speed, swap freely
- **A Base-compatible wallet** — MetaMask or Coinbase Wallet, funded with Base Sepolia testnet ETH (free from a faucet) — needed for both `sibyl init` (SIWE sign-in) and the Base commitment contract (Phase 15)
- **Foundry** (`forge`, `cast`, `anvil`) — for compiling and deploying the minimal commitment contract; lighter-weight than Hardhat for a single-contract hackathon build
- **Docker** — optional, only for the final backend container (Phase 24-equivalent); not needed for local dev since Sibyl is a local SQLite file and Synthea runs once to generate data

**macOS:**
```bash
brew install openjdk@21 gradle uv foundry
```

**Ubuntu/WSL:**
```bash
sudo apt-get update
sudo apt-get install -y openjdk-21-jdk
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -L https://foundry.paradigm.xyz | bash && foundryup
# gradle: use Synthea's own ./gradlew wrapper, no separate install needed
```

**Get Base Sepolia testnet ETH now, not on Day 9:** `https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet` or the Base docs' faucet list. This has nothing to do with Sibyl and is easy to forget until you're blocked on Phase 15.

---

# 4. Phase 1 — Sibyl Memory: Install, Activate, Verify

This phase exists so that every assumption in §0 gets resolved with real output on your machine before any clinical-modeling code gets written. Do not skip steps here — a wrong assumption about tenant scoping (§0.3) discovered on Day 6 instead of Day 1 is expensive.

## 4.1 Install and activate

```bash
cd backend
uv venv && source .venv/bin/activate
uv pip install 'sibyl-memory-client'
uv pip install 'sibyl-memory-cli[mcp]'   # for `sibyl` CLI commands, one-time setup use
```

```bash
sibyl init
```

This opens a browser sign-in page — sign with the same wallet you funded with Base Sepolia ETH in Phase 0 (or email + code if you'd rather keep wallet auth separate for now; either works, free tier requires no card). Credentials land in `~/.sibyl-memory/credentials.json` at mode `0600`.

```bash
sibyl status
```

Confirm you see `Tier FREE`, a `Cap bytes 2,097,152` line, and `DB size` near zero on a fresh install. **Screenshot or copy this output into `schema/sibyl-verified-facts.md`** — you'll want the baseline number to compare against as you ingest data later.

```bash
sibyl health
```

Confirms schema version, DB path, and tenant — **this is your first real signal about the tenant question in §0.3.** Note exactly what "tenant" prints here.

## 4.2 Resolve the tenant_id question (§0.3) — do not proceed past this without an answer

```python
# scripts/verify_sibyl.py — run this before writing any ontology or ingestion code
import inspect
from sibyl_memory_client import MemoryClient

print("MemoryClient.local signature:", inspect.signature(MemoryClient.local))

memory = MemoryClient.local("~/.sibyl-memory/memory.db")
print("set_entity signature:", inspect.signature(memory.set_entity))
print("get_entity signature:", inspect.signature(memory.get_entity))
print("write_event signature:", inspect.signature(memory.write_event))

# Does the client, or the method, accept a tenant_id override at all?
import sibyl_memory_client
print(dir(memory))
print(sibyl_memory_client.__file__)  # locate the installed package to read the real source if signatures are ambiguous
```

Run it:
```bash
python scripts/verify_sibyl.py
```

**Read the printed signatures.** If you see a `tenant_id` parameter anywhere in `MemoryClient.local(...)` or on the per-call methods, use the **tenant-per-patient design** (§0.3, option A) for the rest of this build — update `sibyl/keys.py` (Phase 4) accordingly before writing more code. If you don't see one, use the **naming-convention design** (§0.3, option B) — this is what the rest of this document assumes by default, so no changes needed if that's the case. Either way, write the actual finding into `schema/sibyl-verified-facts.md` so nobody re-derives this halfway through the build.

If the printed signature is genuinely ambiguous (e.g. `**kwargs` swallows everything and you can't tell from `inspect` alone), read the installed source directly:
```bash
python -c "import sibyl_memory_client, os; print(os.path.dirname(sibyl_memory_client.__file__))"
# then open client.py in that directory and read the real implementation
```
This is not a hack — reading an installed open-source package's source when docs are silent on a specific signature is the correct move, not a workaround.

## 4.3 Round-trip verification

```python
# continue in scripts/verify_sibyl.py, or a fresh script
from sibyl_memory_client import MemoryClient

memory = MemoryClient.local("~/.sibyl-memory/memory.db")

memory.set_entity("smoke_test", "probe", {"status": "ok", "n": 1})
result = memory.get_entity("smoke_test", "probe")
print("round trip:", result)
assert result["status"] == "ok"

memory.write_event(acted=["smoke test event written"])
events = memory.read_events()
print("events:", events)

hits = memory.search_entities("probe")
print("search:", hits)
assert len(hits) >= 1

memory.archive_entity("smoke_test", "probe")
print("archived, not deleted — probe should be gone from active search, still on disk")
```

## 4.4 Probe the exact shapes you'll rely on later — write these down, don't assume

Before writing the ingestion pipeline, run each of these once and record the **real** return shape, the same discipline as any other unverified-SDK situation:

```python
# What does read_events() actually return without arguments? All events? Paginated?
print(memory.read_events())

# Does it accept a time range, a kind filter, a limit? Try the plausible kwargs and see what doesn't raise.
import inspect
print(inspect.signature(memory.read_events))

# What does get_entity return for a nonexistent (kind, name)? None? Raise? Empty dict?
try:
    print(memory.get_entity("nonexistent_kind", "nonexistent_name"))
except Exception as e:
    print("raises:", type(e), e)

# What does search_entities return per hit — just names, or full bodies?
print(memory.search_entities("probe"))
```

Write the real answers into `schema/sibyl-verified-facts.md` under a "Confirmed return shapes" heading. Phase 5's repository wrapper is written against whatever you find here — treat the code in that phase as a first draft to adjust, not gospel, the same way you'd treat any code written before its dependency's exact behavior was confirmed.

## 4.5 Phase 1 exit checklist

```text
[ ] sibyl init succeeded, credentials.json exists at 0600
[ ] sibyl status shows Tier FREE, Cap bytes 2,097,152, DB size near zero
[ ] sibyl health passes and prints a tenant value — recorded
[ ] tenant_id question resolved: tenant-per-patient OR naming-convention — decided and written down
[ ] set_entity / get_entity round trip works
[ ] write_event / read_events round trip works, real return shape recorded
[ ] search_entities returns the smoke-test entity
[ ] archive_entity removes it from search but memory.db file still contains it (check file size didn't drop to zero)
[ ] get_entity on a nonexistent key's behavior recorded (None vs. exception vs. empty)
```

Do not write ontology, ingestion, or context-engine code until every line above is checked and recorded.


---

# 5. Phase 2 — Backend Skeleton

```bash
cd backend
uv init --package memora
uv add fastapi uvicorn pydantic pydantic-settings sibyl-memory-client openai web3 eth-account
uv add --dev pytest pytest-asyncio httpx ruff
```

`pyproject.toml` essentials:

```toml
[project]
name = "memora"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sibyl-memory-client",
    "openai>=1.54",
    "web3>=7.5",
    "eth-account>=0.13",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

`.env.example`:

```env
ENVIRONMENT=development
LOG_LEVEL=info

SIBYL_DB_PATH=~/.sibyl-memory/memory.db
SIBYL_TENANT_MODE=naming_convention   # or "native_tenant" — set per your Phase 1 finding

LLM_BASE_URL=https://api.cerebras.ai/v1
LLM_API_KEY=
LLM_MODEL=llama-3.3-70b

BASE_RPC_URL=https://sepolia.base.org
BASE_PRIVATE_KEY=
BASE_COMMITMENT_CONTRACT_ADDRESS=

MAX_EVIDENCE_ITEMS=8
GATE_STRICT_MODE=true
```

Startup sequence:

```text
loadConfig()
  -> connect Sibyl (open MemoryClient.local, run sibyl.health-equivalent check)
  -> connect LLM client
  -> connect Base client (lazy — only needed at commitment time, not every request)
  -> register FastAPI routes
  -> start server
```

Fail fast if `SIBYL_DB_PATH` doesn't exist or isn't readable — never start the app pointed at a Sibyl store that hasn't been through Phase 1's verification.

---

# 6. Phase 3 — Config

`memora/config.py`:

```python
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "info"

    sibyl_db_path: Path = Path("~/.sibyl-memory/memory.db").expanduser()
    sibyl_tenant_mode: Literal["naming_convention", "native_tenant"] = "naming_convention"

    llm_base_url: str
    llm_api_key: str = ""
    llm_model: str

    base_rpc_url: str = "https://sepolia.base.org"
    base_private_key: str = ""
    base_commitment_contract_address: str = ""

    max_evidence_items: int = 8
    gate_strict_mode: bool = True


settings = Settings()

if not settings.sibyl_db_path.exists():
    raise RuntimeError(
        f"Sibyl memory DB not found at {settings.sibyl_db_path}. "
        "Run `sibyl init` and Phase 1's verify_sibyl.py before starting the app."
    )
```


---

# 7. Phase 4 — Patient Key & Naming Strategy

This is MEMORA's equivalent of "the id strategy" — the single place that decides how a patient's data stays isolated and findable, written once, used everywhere else so nothing downstream has to re-derive it.

`memora/sibyl/keys.py`:

```python
"""
Every piece of clinical data MEMORA writes is scoped to one patient. Because
the exact tenant_id mechanism was unconfirmed in the public SDK docs (see
README §0.3), this module implements BOTH strategies behind one interface —
set SIBYL_TENANT_MODE in .env to whichever Phase 1 confirmed on your
installed package version, and nothing outside this file needs to change.
"""

from dataclasses import dataclass
from memora.config import settings


@dataclass(frozen=True)
class PatientScope:
    patient_id: str  # e.g. "P-10482" — synthetic, never a real identifier

    def kind(self, base_kind: str) -> str:
        """The `kind` argument passed to set_entity/get_entity."""
        return base_kind

    def name(self, entity_name: str) -> str:
        """The `name` argument passed to set_entity/get_entity."""
        if settings.sibyl_tenant_mode == "native_tenant":
            return entity_name  # isolation comes from tenant_id itself, not the name
        return f"{self.patient_id}::{entity_name}"  # naming-convention fallback

    def tenant_kwargs(self) -> dict:
        """Extra kwargs to splice into every Sibyl call, if native tenancy is confirmed available."""
        if settings.sibyl_tenant_mode == "native_tenant":
            return {"tenant_id": f"patient-{self.patient_id}"}
        return {}

    def search_prefix(self) -> str:
        """Prepend to every search_entities() query so FTS5 matches stay patient-scoped
        under naming-convention mode. Under native_tenant mode this is unnecessary —
        tenant scoping already restricts search results."""
        if settings.sibyl_tenant_mode == "native_tenant":
            return ""
        return f"{self.patient_id} "


# Every `kind` string MEMORA writes, centralized so a typo can't silently create
# a new, unsearchable category. See memora/ontology/kinds.py for the full list
# and what tier each maps to.
```

**Why this matters even if the naming-convention fallback is what you end up using:** under that mode, `search_entities("drug a")` with no patient scoping could theoretically surface another patient's "drug a" entity, since FTS5 has no built-in tenant filter to lean on if you're not using real `tenant_id` isolation. `search_prefix()` mitigates this by making every query patient-scoped in its query text — but this is a **soft** boundary (text matching), not a hard one (schema-level constraint) the way native `tenant_id` would be. If Phase 1 confirmed native tenancy is available, use it — it's strictly safer, and this file is built so that's a one-line config change, not a rewrite.

---

# 8. Phase 5 — Sibyl Repository Layer

The one place every Sibyl call in MEMORA actually happens. Every other module imports this, never `sibyl_memory_client` directly — same discipline as the HydraDB build's repository facade: one audited chokepoint, not scattered raw calls.

`memora/sibyl/errors.py`:

```python
class SibylQuotaExceededError(Exception):
    """Raised when a write would exceed the free-tier 2 MiB cap (§0.2)."""


class SibylUnavailableError(Exception):
    """Raised when the local Sibyl DB file can't be opened at all."""
```

`memora/sibyl/client.py`:

```python
from sibyl_memory_client import MemoryClient
from memora.config import settings
from memora.sibyl.keys import PatientScope
from memora.sibyl.errors import SibylQuotaExceededError, SibylUnavailableError

QUOTA_WARN_THRESHOLD_BYTES = int(2_097_152 * 0.85)  # warn at 85% of the free-tier cap


class PatientMemory:
    """Patient-scoped facade over Sibyl's five tiers. Every method here maps
    directly to one Sibyl SDK call — this class adds scoping and quota
    awareness, nothing else. It does NOT add caching, retries with silent
    fallback, or any behavior that could let the app answer without a real
    Sibyl round trip — that would fail the deletion test (README §0.4)."""

    def __init__(self, patient_id: str):
        try:
            self._memory = MemoryClient.local(str(settings.sibyl_db_path))
        except Exception as e:
            raise SibylUnavailableError(f"Could not open Sibyl memory store: {e}") from e
        self.scope = PatientScope(patient_id=patient_id)

    # ---- HOT: current situational context ----
    def set_context(self, key: str, body: dict) -> None:
        self._check_quota()
        self._memory.set_state(self.scope.name(key), body, **self.scope.tenant_kwargs())

    def get_context(self, key: str) -> dict | None:
        return self._memory.get_state(self.scope.name(key), **self.scope.tenant_kwargs())

    # ---- WARM: current clinical facts ----
    def set_fact(self, kind: str, name: str, body: dict) -> None:
        self._check_quota()
        self._memory.set_entity(self.scope.kind(kind), self.scope.name(name), body, **self.scope.tenant_kwargs())

    def get_fact(self, kind: str, name: str) -> dict | None:
        return self._memory.get_entity(self.scope.kind(kind), self.scope.name(name), **self.scope.tenant_kwargs())

    # ---- COLD: append-only history ----
    def log_event(self, description: str, **metadata) -> None:
        self._check_quota()
        self._memory.write_event(acted=[description], **metadata, **self.scope.tenant_kwargs())

    def read_history(self, **filters) -> list:
        return self._memory.read_events(**filters, **self.scope.tenant_kwargs())

    # ---- REFERENCE: static lookup docs (protocols, policy text) ----
    def set_reference(self, key: str, body: dict) -> None:
        self._check_quota()
        self._memory.set_reference(self.scope.name(key), body, **self.scope.tenant_kwargs())

    def get_reference(self, key: str) -> dict | None:
        return self._memory.get_reference(self.scope.name(key), **self.scope.tenant_kwargs())

    # ---- ARCHIVE: retire, never delete ----
    def archive_fact(self, kind: str, name: str) -> None:
        self._memory.archive_entity(self.scope.kind(kind), self.scope.name(name), **self.scope.tenant_kwargs())
        # NEVER call delete_entity on clinical data. If you find yourself
        # reaching for it, you want archive_fact instead — see README §1.2.

    # ---- Search ----
    def search(self, query: str) -> list:
        scoped_query = f"{self.scope.search_prefix()}{query}"
        return self._memory.search_entities(scoped_query)

    def _check_quota(self) -> None:
        db_size = settings.sibyl_db_path.stat().st_size
        if db_size >= 2_097_152:
            raise SibylQuotaExceededError(
                f"Sibyl free-tier 2 MiB cap reached ({db_size} bytes). "
                "Trim the synthetic dataset or upgrade the account (see README §0.2)."
            )
        if db_size >= QUOTA_WARN_THRESHOLD_BYTES:
            import logging
            logging.getLogger("memora.sibyl").warning(
                "Sibyl DB at %d bytes — %.0f%% of the free-tier cap", db_size, 100 * db_size / 2_097_152
            )
```

**One deliberate omission, worth calling out:** there is no `try/except` anywhere in this class that swallows a Sibyl error and returns a default value. Every failure propagates. This is not an oversight — a repository layer that quietly falls back to "no data" or a cached value on a Sibyl error is exactly the kind of hidden path that fails the deletion test later, even by accident. Let it raise; handle the failure explicitly and visibly at the call site (the Context Engine and Gate, §9/§11, already do — they turn a Sibyl failure into an explicit "cannot verify" response, not a silent guess).


---

# 9. Phase 6 — Clinical Ontology (mapped onto Sibyl's five tiers)

`memora/ontology/kinds.py`:

```python
"""
Every `kind` string MEMORA writes to Sibyl WARM entities, in one place, so
naming stays FTS5-search-friendly and consistent between ingestion and
retrieval. Sibyl's search is keyword text matching (README §0.1) — these
strings ARE the retrieval surface, not just internal labels.
"""

# WARM — current state, one row per (kind, name), overwritten on update
KIND_MEDICATION = "medication"          # current medication status
KIND_ALLERGY = "allergy"                # documented adverse reactions / contraindications
KIND_DIAGNOSIS = "diagnosis"            # active problem list
KIND_PROCEDURE_STATUS = "procedure"     # status of a procedure (scheduled/done/complication)
KIND_LAB_TREND = "lab_trend"            # latest value + trend direction for a tracked lab
KIND_CARE_PHASE = "care_phase"          # current admission/transition status

# HOT — current situational context, keyed by session/task, not by patient fact
STATE_KEY_ACTIVE_SITUATION = "active_situation"   # {situation, clinician_role, task}

# REFERENCE — static lookup content
REF_KEY_POLICY = "clinical_policy"       # the Gate's declared policy rules (Phase 11)
REF_KEY_PROTOCOL_PREFIX = "protocol"     # e.g. "protocol::icu_to_ward_checklist"
```

`memora/ontology/events.py`:

```python
"""
COLD journal event schema. write_event(acted=[...]) is Sibyl's only append-only
write path (README §0.1) — every clinically important thing that HAPPENED (as
opposed to what's currently TRUE, which lives in WARM) goes through this
schema so read_history() results are structured the same way every time.
"""

from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ClinicalEvent:
    event_type: str          # "medication_administered" | "adverse_reaction" | "medication_discontinued" |
                              # "lab_result" | "procedure_performed" | "complication" | "handoff" | "diagnosis_made"
    summary: str              # human-readable, one line — this is what acted=[...] carries
    timestamp: str             # ISO 8601 — Synthea provides this natively
    related_kind: str | None = None   # links back to a WARM entity kind, if any
    related_name: str | None = None   # links back to a WARM entity name, if any
    source_id: str | None = None       # Synthea's own record id, for provenance
    severity: str | None = None         # "info" | "warning" | "critical" — used by the Gate

    def to_acted_string(self) -> str:
        """Sibyl's write_event only takes acted=[str, ...] per the documented
        example — we pack structure into a single descriptive line and rely
        on read_history()'s raw event text for the Evidence Resolver to parse
        back out. VERIFY in Phase 1 (§4.4) whether write_event also accepts
        arbitrary metadata kwargs that survive into read_events() — if so,
        prefer passing structured fields directly instead of string-packing."""
        return f"[{self.event_type}] {self.summary} (source={self.source_id}, severity={self.severity})"
```

## 9.1 Tier mapping, explicit

| Clinical concept | Sibyl tier | Why |
|---|---|---|
| "Drug A is currently contraindicated" | WARM (`medication`) | Current state — single row, overwritten as it changes |
| "Drug A was administered, caused a reaction, was discontinued" | COLD (journal) | History — append-only, three separate events, never overwritten |
| "Receiving clinician is doing medication reconciliation for ICU→ward" | HOT (`active_situation`) | Ephemeral, current-task context |
| "Standard ICU→ward handoff checklist" | REFERENCE | Static, looked up by name, not patient-specific |
| "Old care-phase status once the patient moves to ward" | ARCHIVE | Retired but recoverable, never hard-deleted |

**The important discipline this table enforces:** a WARM write and a COLD event are not alternatives to each other — they're always a *pair* for anything that represents a change. When Drug A gets discontinued, the ingestion pipeline (Phase 8) does both: `set_fact("medication", "drug_a", {"status": "discontinued", ...})` **and** `log_event("Drug A discontinued after documented adverse reaction", event_type="medication_discontinued", ...)`. The WARM write alone loses the "why" and "when it changed"; the COLD event alone doesn't tell you what's true *right now* without replaying the whole journal. Skipping either one breaks something downstream — skip the WARM write and `CURRENT_STATE`-style queries have nothing to read; skip the COLD event and the Evidence Resolver has no source event to cite.


---

# 10. Phase 7 — Synthea: Generate & Parse Synthetic Patients

## 10.1 Build and run Synthea

```bash
cd vendor
git clone https://github.com/synthetichealth/synthea.git
cd synthea
./gradlew build check -x test    # -x test skips Synthea's own slow test suite, not needed for our use
```

Given the 2 MiB Sibyl quota (§0.2), generate a **small, targeted** population, not Synthea's usual thousands-of-patients default:

```bash
./run_synthea -p 15 --exporter.fhir.export true --exporter.baseDirectory ./output Massachusetts
```

`-p 15` generates 15 patients — enough to pick 3-8 genuinely interesting "story patients" with real longitudinal complexity (multiple admissions, medication changes, at least one documented adverse reaction) without blowing the quota. Output lands in `vendor/synthea/output/fhir/*.json`, one FHIR R4 Bundle per patient.

**Pick story patients deliberately, don't take the first N.** Write a quick filter script:

```python
# scripts/find_story_patients.py — run once, by hand, to pick your demo patients
import json
from pathlib import Path

for path in Path("vendor/synthea/output/fhir").glob("*.json"):
    bundle = json.loads(path.read_text())
    resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    med_requests = resource_types.count("MedicationRequest")
    encounters = resource_types.count("Encounter")
    allergies = resource_types.count("AllergyIntolerance")
    if med_requests >= 3 and encounters >= 5 and allergies >= 1:
        print(f"{path.name}: {med_requests} meds, {encounters} encounters, {allergies} allergies — GOOD CANDIDATE")
```

## 10.2 Parse FHIR into MEMORA's internal event schema

FHIR Bundles are verbose and generic — MEMORA needs its own `ClinicalEvent` objects (Phase 6), in chronological order, per patient.

`memora/ingest/synthea_parser.py`:

```python
import json
from pathlib import Path
from memora.ontology.events import ClinicalEvent

# Minimal FHIR resourceType -> ClinicalEvent mapping. Extend as your story
# patients need more resource types — this covers the flagship ICU->ward
# workflow's needs (medications, allergies, encounters, procedures,
# conditions) without trying to parse all of FHIR R4.

def parse_patient_bundle(path: Path) -> tuple[str, list[ClinicalEvent]]:
    bundle = json.loads(path.read_text())
    patient_resource = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient")
    patient_id = patient_resource["id"]

    events: list[ClinicalEvent] = []

    for entry in bundle["entry"]:
        resource = entry["resource"]
        rtype = resource["resourceType"]

        if rtype == "MedicationRequest":
            events.append(ClinicalEvent(
                event_type="medication_administered",
                summary=f"{resource.get('medicationCodeableConcept', {}).get('text', 'Unknown medication')} prescribed",
                timestamp=resource.get("authoredOn", ""),
                related_kind="medication",
                related_name=_slug(resource.get("medicationCodeableConcept", {}).get("text", "unknown")),
                source_id=resource["id"],
            ))

        elif rtype == "AllergyIntolerance":
            events.append(ClinicalEvent(
                event_type="adverse_reaction",
                summary=f"Documented reaction: {resource.get('code', {}).get('text', 'unspecified')}",
                timestamp=resource.get("recordedDate", ""),
                related_kind="allergy",
                related_name=_slug(resource.get("code", {}).get("text", "unknown")),
                source_id=resource["id"],
                severity="critical",
            ))

        elif rtype == "Encounter":
            events.append(ClinicalEvent(
                event_type="handoff",
                summary=f"Encounter: {resource.get('type', [{}])[0].get('text', 'visit')}",
                timestamp=resource.get("period", {}).get("start", ""),
                source_id=resource["id"],
            ))

        elif rtype == "Procedure":
            events.append(ClinicalEvent(
                event_type="procedure_performed",
                summary=resource.get("code", {}).get("text", "Procedure performed"),
                timestamp=resource.get("performedDateTime", resource.get("performedPeriod", {}).get("start", "")),
                related_kind="procedure",
                related_name=_slug(resource.get("code", {}).get("text", "unknown")),
                source_id=resource["id"],
            ))

        elif rtype == "Condition":
            events.append(ClinicalEvent(
                event_type="diagnosis_made",
                summary=resource.get("code", {}).get("text", "Diagnosis recorded"),
                timestamp=resource.get("recordedDate", resource.get("onsetDateTime", "")),
                related_kind="diagnosis",
                related_name=_slug(resource.get("code", {}).get("text", "unknown")),
                source_id=resource["id"],
            ))

    events = [e for e in events if e.timestamp]  # drop anything without a real timestamp — can't order it
    events.sort(key=lambda e: e.timestamp)
    return patient_id, events


def _slug(text: str) -> str:
    return text.lower().strip().replace(" ", "_").replace("/", "_")[:60]
```

**Note the FHIR parsing here is deliberately narrow** — five resource types, not a general FHIR R4 client. That's correct for a 10-day hackathon scope: MEMORA doesn't need a production FHIR importer, it needs enough real structure to make the ICU→ward demo credible. If a story patient's interesting complexity lives in a resource type not listed here (e.g. `Observation` for lab trends), add one more `elif` branch — don't build a generic FHIR mapper speculatively.


---

# 11. Phase 8 — Ingestion Pipeline (Change Detection + Sibyl Writes)

`memora/ingest/change_detector.py`:

```python
"""
Sibyl WARM entities overwrite in place (README §0.1 — UNIQUE per (kind, name)).
There's no built-in versioning. This module is what preserves the "same idea,
superseded not deleted" principle on top of that: before overwriting a WARM
fact, check what was there, and if it's a real change, log it as a COLD event
BEFORE the overwrite happens — so the history survives even though the WARM
row itself doesn't keep old values.
"""

from memora.sibyl.client import PatientMemory
from memora.ontology.events import ClinicalEvent


def apply_fact_change(memory: PatientMemory, kind: str, name: str, new_body: dict, change_event: ClinicalEvent) -> str:
    """Returns 'new' | 'confirmed' | 'changed'."""
    existing = memory.get_fact(kind, name)

    if existing is None:
        memory.set_fact(kind, name, new_body)
        memory.log_event(change_event.to_acted_string(), event_type=change_event.event_type,
                          timestamp=change_event.timestamp, source_id=change_event.source_id,
                          severity=change_event.severity)
        return "new"

    if existing == new_body:
        return "confirmed"  # nothing changed, no redundant write, no redundant event

    # A real change: log the transition explicitly, THEN overwrite.
    # The event summary captures the before/after so a fact's history is
    # reconstructible by reading the journal even though WARM only shows "now."
    transition_event = ClinicalEvent(
        event_type=change_event.event_type,
        summary=f"{change_event.summary} (previously: {existing})",
        timestamp=change_event.timestamp,
        related_kind=kind,
        related_name=name,
        source_id=change_event.source_id,
        severity=change_event.severity,
    )
    memory.log_event(transition_event.to_acted_string(), event_type=transition_event.event_type,
                      timestamp=transition_event.timestamp, source_id=transition_event.source_id,
                      severity=transition_event.severity)
    memory.set_fact(kind, name, new_body)
    return "changed"
```

`memora/ingest/pipeline.py`:

```python
from pathlib import Path
from memora.sibyl.client import PatientMemory
from memora.ingest.synthea_parser import parse_patient_bundle
from memora.ingest.change_detector import apply_fact_change
from memora.ontology.kinds import KIND_MEDICATION, KIND_ALLERGY, KIND_DIAGNOSIS, KIND_PROCEDURE_STATUS


def ingest_patient(bundle_path: Path) -> dict:
    patient_id, events = parse_patient_bundle(bundle_path)
    memory = PatientMemory(patient_id=patient_id)

    counts = {"new": 0, "confirmed": 0, "changed": 0}

    for event in events:
        if event.related_kind == "allergy":
            result = apply_fact_change(memory, KIND_ALLERGY, event.related_name,
                                        {"status": "documented", "reaction": event.summary}, event)
        elif event.related_kind == "medication":
            status = "discontinued" if "discontinu" in event.summary.lower() else "active"
            result = apply_fact_change(memory, KIND_MEDICATION, event.related_name,
                                        {"status": status}, event)
        elif event.related_kind == "procedure":
            result = apply_fact_change(memory, KIND_PROCEDURE_STATUS, event.related_name,
                                        {"status": "performed"}, event)
        elif event.related_kind == "diagnosis":
            result = apply_fact_change(memory, KIND_DIAGNOSIS, event.related_name,
                                        {"status": "active"}, event)
        else:
            # Pure history, no WARM state to track (e.g. a plain handoff/encounter marker)
            memory.log_event(event.to_acted_string(), event_type=event.event_type,
                              timestamp=event.timestamp, source_id=event.source_id)
            result = "new"

        counts[result if result in counts else "new"] += 1

    return {"patient_id": patient_id, "events_processed": len(events), **counts}
```

`scripts/ingest_demo.py`:

```python
"""Run once to populate Sibyl with your chosen story patients. Prints DB size
after every patient so you catch the quota cap (§0.2) before it surprises you
mid-demo, not during it."""

from pathlib import Path
from memora.ingest.pipeline import ingest_patient
from memora.config import settings

STORY_PATIENTS = [
    # fill in with the filenames from scripts/find_story_patients.py's output
    "vendor/synthea/output/fhir/Patient_example_1.json",
]

for path_str in STORY_PATIENTS:
    result = ingest_patient(Path(path_str))
    db_size = settings.sibyl_db_path.stat().st_size
    print(f"{result} — DB now {db_size:,} bytes ({100*db_size/2_097_152:.1f}% of free-tier cap)")
```


---

# 12. Phase 9 — Context Engine (the "situation-aware retrieval" layer)

This is MEMORA's compiler-equivalent: a typed situation goes in, a bounded, deterministic retrieval plan comes out. Same situation + same patient memory ⇒ same plan, every time — no ad-hoc query construction from free text.

`memora/context/situations.py`:

```python
from enum import Enum


class Situation(str, Enum):
    ICU_TO_WARD = "icu_to_ward"
    PRE_OPERATIVE = "pre_operative"
    DISCHARGE = "discharge"


class ClinicianRole(str, Enum):
    WARD_PHYSICIAN = "ward_physician"
    SURGEON = "surgeon"
    ICU_PHYSICIAN = "icu_physician"


# What each situation cares about — this table IS the "compiler" for the
# retrieval side. Same shape as an operation-to-query-template registry;
# adding a new situation means adding one row here, not new ad-hoc logic
# scattered through the codebase.
SITUATION_FOCUS = {
    Situation.ICU_TO_WARD: {
        "kinds": ["medication", "allergy", "lab_trend", "diagnosis"],
        "event_types": ["adverse_reaction", "medication_discontinued", "lab_result", "complication"],
        "task": "medication_reconciliation",
    },
    Situation.PRE_OPERATIVE: {
        "kinds": ["allergy", "procedure", "medication"],
        "event_types": ["adverse_reaction", "complication", "procedure_performed"],
        "task": "pre_operative_review",
    },
    Situation.DISCHARGE: {
        "kinds": ["diagnosis", "medication", "procedure"],
        "event_types": ["diagnosis_made", "medication_administered", "procedure_performed"],
        "task": "continuity_of_care",
    },
}
```

`memora/context/engine.py`:

```python
from dataclasses import dataclass
from memora.sibyl.client import PatientMemory
from memora.context.situations import Situation, ClinicianRole, SITUATION_FOCUS
from memora.config import settings


@dataclass
class RetrievalPlan:
    patient_id: str
    situation: Situation
    role: ClinicianRole
    kinds_to_check: list[str]
    event_types_to_check: list[str]
    max_items: int


def compile_plan(patient_id: str, situation: Situation, role: ClinicianRole) -> RetrievalPlan:
    """Pure function: same inputs, same plan, every time. This is the whole
    reason 'the same patient memory produces different relevant subsets for
    different situations' (the core innovation claim) is actually true by
    construction, not just true in the demo script."""
    focus = SITUATION_FOCUS[situation]
    return RetrievalPlan(
        patient_id=patient_id,
        situation=situation,
        role=role,
        kinds_to_check=focus["kinds"],
        event_types_to_check=focus["event_types"],
        max_items=settings.max_evidence_items,
    )


def execute_plan(plan: RetrievalPlan) -> dict:
    """Executes the plan against Sibyl. Returns raw facts + raw history,
    unranked — the Evidence Resolver (Phase 10) is where relevance selection
    and evidence-linking actually happen. This function's only job is a
    faithful, bounded read from Sibyl."""
    memory = PatientMemory(patient_id=plan.patient_id)

    # Record the active situation in HOT state — this is what makes the
    # "current context" genuinely part of memory, inspectable via get_context,
    # not just a Python variable that disappears when the request ends.
    memory.set_context("active_situation", {
        "situation": plan.situation.value,
        "role": plan.role.value,
    })

    facts = {}
    for kind in plan.kinds_to_check:
        # Sibyl's SDK doesn't document a "list all entities of a kind" call
        # (only get_entity by exact name) — use search_entities scoped to the
        # kind as a keyword, and verify this actually surfaces what you expect
        # in Phase 1's follow-up testing once real data is loaded.
        hits = memory.search(kind)
        facts[kind] = hits[: plan.max_items]

    history = memory.read_history()
    relevant_history = [
        h for h in history
        if any(et in str(h) for et in plan.event_types_to_check)
    ][: plan.max_items]

    return {"facts": facts, "history": relevant_history}
```

**Worth being honest about here:** `search_entities` as a "list everything of kind X" mechanism is a workaround, not a documented feature — the SDK's example only shows exact-name `get_entity` lookups and free-text `search_entities`. This is exactly the kind of thing Phase 1's probing (§4.4) should stress-test once real patient data is loaded: run `memory.search("medication")` against a patient with three medications and confirm all three come back, not just the best keyword match. If it under-returns, the fallback is to track a small WARM "index" entity per kind (e.g. `set_entity("medication_index", patient_id, {"names": [...]})`) that the ingestion pipeline maintains alongside each write — more code, but guaranteed complete rather than dependent on FTS ranking behavior.


---

# 13. Phase 10 — Evidence Resolver

Every claim the LLM proposes gets checked against what's actually in Sibyl before it's allowed to be shown as verified. This is the piece that makes "evidence-linked" a code-level guarantee, not a UI label.

`memora/evidence/resolver.py`:

```python
from dataclasses import dataclass
from memora.sibyl.client import PatientMemory


@dataclass
class EvidenceCheck:
    claim_text: str
    supported: bool
    source_kind: str | None = None
    source_name: str | None = None
    source_event: str | None = None
    reason: str | None = None  # populated when NOT supported


def resolve_claim(memory: PatientMemory, claim_text: str, related_kind: str | None, related_name: str | None) -> EvidenceCheck:
    """
    Deliberately narrow: this does NOT use the LLM to decide if a claim is
    supported — that would put the model back in charge of its own grading.
    It checks whether a WARM fact or COLD event actually exists that the
    claim could be citing. If the LLM's proposal didn't come with a
    (related_kind, related_name) pointer at all, that itself is a failure —
    an unsourced claim is not evidence, regardless of how it reads.
    """
    if related_kind is None or related_name is None:
        return EvidenceCheck(claim_text=claim_text, supported=False,
                              reason="Proposal cited no source entity — cannot verify against memory.")

    fact = memory.get_fact(related_kind, related_name)
    if fact is not None:
        return EvidenceCheck(claim_text=claim_text, supported=True,
                              source_kind=related_kind, source_name=related_name)

    history = memory.read_history()
    matching_events = [h for h in history if related_name.replace("_", " ") in str(h).lower()]
    if matching_events:
        return EvidenceCheck(claim_text=claim_text, supported=True,
                              source_kind=related_kind, source_name=related_name,
                              source_event=str(matching_events[0]))

    return EvidenceCheck(claim_text=claim_text, supported=False,
                          reason=f"No WARM fact or COLD event found for ({related_kind}, {related_name}).")


def resolve_all(memory: PatientMemory, proposed_claims: list[dict]) -> list[EvidenceCheck]:
    return [
        resolve_claim(memory, c["text"], c.get("related_kind"), c.get("related_name"))
        for c in proposed_claims
    ]
```

---

# 14. Phase 11 — Deterministic Safety Gate

One function, three checks, as agreed in the scope-cut discussion — not three separate orchestrated "agents," a single auditable decision point. This is the piece the rules' *"coordination and dynamic-storage patterns top the band"* language is specifically rewarding, and it's also the piece that makes Sibyl load-bearing for the *decision*, not just for the *answer text*.

`memora/gate/policy.py`:

```python
"""
Declared clinical policy rules — deterministic, not LLM-interpreted. Kept
intentionally small and explicit for the hackathon scope: real policy
authoring is out of scope, a demonstrable mechanism is in scope.
"""

POLICY_RULES = {
    # A claim about a medication that has a documented adverse reaction on
    # file can never be silently "allowed" — it always requires explicit
    # surfacing, regardless of what the LLM proposed.
    "adverse_reaction_medication": {
        "description": "Medications with a documented adverse reaction must be flagged, never presented as safe.",
        "blocks_if": lambda fact: fact is not None and fact.get("status") == "contraindicated",
    },
    # An unverified claim can never be marked as clinically confirmed output.
    "unverified_claim": {
        "description": "Claims with no supporting Sibyl record cannot be presented as verified.",
        "blocks_if": lambda evidence_check: not evidence_check.supported,
    },
}
```

`memora/gate/authority.py`:

```python
"""
Minimal role/task permission table — the "authority" check. Two hardcoded
personas per the scope-cut plan (README's earlier discussion): full RBAC is
explicitly out of scope for the hackathon build.
"""

from memora.context.situations import ClinicianRole

ROLE_PERMISSIONS = {
    ClinicianRole.WARD_PHYSICIAN: {"can_view": ["medication", "allergy", "diagnosis"], "can_approve_handoff": True},
    ClinicianRole.SURGEON: {"can_view": ["allergy", "procedure", "medication"], "can_approve_handoff": False},
    ClinicianRole.ICU_PHYSICIAN: {"can_view": ["medication", "allergy", "diagnosis", "lab_trend"], "can_approve_handoff": True},
}


def has_authority(role: ClinicianRole, kind: str) -> bool:
    return kind in ROLE_PERMISSIONS.get(role, {}).get("can_view", [])
```

`memora/gate/gate.py`:

```python
from dataclasses import dataclass
from enum import Enum
from memora.sibyl.client import PatientMemory
from memora.context.situations import ClinicianRole
from memora.evidence.resolver import EvidenceCheck
from memora.gate.policy import POLICY_RULES
from memora.gate.authority import has_authority


class GateResult(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class GateDecision:
    result: GateResult
    reason: str
    evidence: EvidenceCheck | None = None


def evaluate_claim(memory: PatientMemory, evidence: EvidenceCheck, role: ClinicianRole) -> GateDecision:
    """
    The one function every proposed claim passes through before it can be
    shown as verified. Three checks, in order, first failure wins:

    1. Evidence check — is this actually supported by Sibyl records?
    2. Policy check — does a declared clinical rule require blocking/flagging?
    3. Authority check — is this clinician's role permitted to view this kind of fact?

    NOTHING in this function can return ALLOW without first calling
    memory.get_fact/read_history through `evidence`, which was itself built
    from a real Sibyl round trip in Phase 10. There is no cached or
    hardcoded fallback path — remove Sibyl, and evidence.supported can never
    legitimately be True, so this function can never legitimately ALLOW
    anything. That's the deletion-test guarantee (README §0.4), enforced
    structurally, not just by intent.
    """
    if not evidence.supported:
        return GateDecision(result=GateResult.BLOCK, reason=evidence.reason or "Unsupported claim.", evidence=evidence)

    if evidence.source_kind and not has_authority(role, evidence.source_kind):
        return GateDecision(result=GateResult.BLOCK,
                             reason=f"Role {role.value} is not authorized to view {evidence.source_kind} facts.",
                             evidence=evidence)

    fact = memory.get_fact(evidence.source_kind, evidence.source_name) if evidence.source_kind else None
    for rule_name, rule in POLICY_RULES.items():
        try:
            triggered = rule["blocks_if"](fact) if "fact" in rule["blocks_if"].__code__.co_varnames else rule["blocks_if"](evidence)
        except Exception:
            continue
        if triggered:
            return GateDecision(result=GateResult.NEEDS_REVIEW,
                                 reason=f"Policy '{rule_name}' triggered: {rule['description']}",
                                 evidence=evidence)

    return GateDecision(result=GateResult.ALLOW, reason="Supported by memory, authorized, no policy conflict.", evidence=evidence)


def evaluate_all(memory: PatientMemory, evidence_checks: list[EvidenceCheck], role: ClinicianRole) -> list[GateDecision]:
    return [evaluate_claim(memory, ec, role) for ec in evidence_checks]
```


---

# 15. Phase 12 — Clinician Roles & Task Profiles

`memora/clinicians/roles.py`:

```python
"""
Two hardcoded personas for the demo — real authentication is explicitly out
of scope for the hackathon build (see the scope-cut discussion in the
planning history). This is enough to demonstrate role-aware retrieval and
authority-gated output, which is what's actually being judged.
"""

from dataclasses import dataclass
from memora.context.situations import ClinicianRole


@dataclass
class Clinician:
    name: str
    role: ClinicianRole


CLINICIANS = {
    "dr_maya": Clinician(name="Dr. Maya", role=ClinicianRole.ICU_PHYSICIAN),
    "dr_arun": Clinician(name="Dr. Arun", role=ClinicianRole.WARD_PHYSICIAN),
}
```

---

# 16. Phase 13 — LLM Proposal Layer

The LLM proposes a clinical brief from the retrieved evidence. It never gets final say — everything it produces here goes through Phase 10/11 before being shown as verified. Uses the same OpenAI-compatible-endpoint pattern already validated for Cerebras/Groq.

`memora/llm/client.py`:

```python
from openai import OpenAI
from memora.config import settings

client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key or "unused")
```

`memora/llm/propose.py`:

```python
import json
from memora.llm.client import client
from memora.config import settings

SYSTEM_PROMPT = """You are a clinical context assistant. Given retrieved patient
facts and history, propose a short list of claims relevant to the current
clinical situation. You are NOT the final authority — every claim you produce
will be independently checked against the source records before being shown
to a clinician. For every claim, you MUST cite which retrieved fact or event
it came from using related_kind and related_name fields matching the input
data exactly. Never state a claim that isn't grounded in the provided facts
and history. If nothing relevant was retrieved, say so explicitly — do not
invent a plausible-sounding clinical fact.

Respond with ONLY a JSON object: {"claims": [{"text": str, "related_kind": str, "related_name": str}, ...]}"""


def propose_claims(facts: dict, history: list) -> list[dict]:
    payload = json.dumps({"facts": facts, "history": history}, default=str)

    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Retrieved data:\n{payload}"},
        ],
    )

    raw = response.choices[0].message.content
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []  # fail closed — no claims proposed rather than garbage passed downstream

    return parsed.get("claims", [])
```


---

# 17. Phase 14 — API Layer

`memora/api/schemas.py`:

```python
from pydantic import BaseModel
from memora.context.situations import Situation, ClinicianRole


class HandoffRequest(BaseModel):
    patient_id: str
    situation: Situation
    clinician_id: str  # "dr_maya" | "dr_arun"


class ClaimResult(BaseModel):
    text: str
    gate_result: str  # ALLOW | BLOCK | NEEDS_REVIEW
    reason: str
    source_kind: str | None = None
    source_name: str | None = None
    source_event: str | None = None


class HandoffResponse(BaseModel):
    patient_id: str
    situation: str
    clinician: str
    claims: list[ClaimResult]
    sibyl_db_size_bytes: int
```

`memora/api/routes.py`:

```python
from fastapi import APIRouter, HTTPException
from memora.api.schemas import HandoffRequest, HandoffResponse, ClaimResult
from memora.context.engine import compile_plan, execute_plan
from memora.evidence.resolver import resolve_all
from memora.gate.gate import evaluate_all
from memora.llm.propose import propose_claims
from memora.clinicians.roles import CLINICIANS
from memora.sibyl.client import PatientMemory
from memora.sibyl.errors import SibylUnavailableError, SibylQuotaExceededError
from memora.config import settings

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/readyz")
def ready():
    try:
        PatientMemory(patient_id="__readyz_probe__")
        return {"status": "ready", "sibyl": True}
    except SibylUnavailableError:
        return {"status": "not_ready", "sibyl": False}


@router.post("/handoff", response_model=HandoffResponse)
def get_handoff(req: HandoffRequest):
    clinician = CLINICIANS.get(req.clinician_id)
    if clinician is None:
        raise HTTPException(status_code=400, detail=f"Unknown clinician_id: {req.clinician_id}")

    try:
        plan = compile_plan(req.patient_id, req.situation, clinician.role)
        retrieved = execute_plan(plan)
    except SibylQuotaExceededError as e:
        raise HTTPException(status_code=507, detail=str(e))
    except SibylUnavailableError as e:
        # THIS is the response a judge sees if they run the deletion test —
        # a clean, explicit failure, never a fabricated answer.
        raise HTTPException(status_code=503, detail=f"Cannot reconstruct patient context: {e}")

    proposed = propose_claims(retrieved["facts"], retrieved["history"])

    memory = PatientMemory(patient_id=req.patient_id)
    evidence_checks = resolve_all(memory, proposed)
    gate_decisions = evaluate_all(memory, evidence_checks, clinician.role)

    claims = [
        ClaimResult(
            text=ec.claim_text,
            gate_result=gd.result.value,
            reason=gd.reason,
            source_kind=ec.source_kind,
            source_name=ec.source_name,
            source_event=ec.source_event,
        )
        for ec, gd in zip(evidence_checks, gate_decisions)
    ]

    return HandoffResponse(
        patient_id=req.patient_id,
        situation=req.situation.value,
        clinician=clinician.name,
        claims=claims,
        sibyl_db_size_bytes=settings.sibyl_db_path.stat().st_size,
    )
```

`memora/main.py`:

```python
from fastapi import FastAPI
from memora.api.routes import router

app = FastAPI(title="MEMORA", version="0.1.0")
app.include_router(router)
```

```bash
uvicorn memora.main:app --reload --port 8080
```


---

# 18. Phase 15 — Base Integrity Commitment

## 18.1 Which option to actually build

The rules accept any of: *"a wallet operation, an x402 payment, a B20 read, or a contract interaction."* Researched all four before choosing:

- **x402** is real and well-documented (Coinbase/Cloudflare, now under the Linux Foundation, live on Base) — but it's built for *paying for API access*, machine-to-machine, using EIP-3009 signed transfer authorizations. Forcing a "payment" into MEMORA's flow (e.g. "pay $0.001 to commit a handoff") is possible but adds a facilitator dependency and signing flow that doesn't serve MEMORA's actual function — it would be exactly the kind of *"claimed stack that is not exercised"* pattern the rules warn about if bolted on artificially.
- **"B20 read"** — not a term either of us could find defined anywhere in Base/Coinbase documentation searched today. Treat as ambiguous; don't design around it.
- **A plain contract interaction** is the correct fit: cheapest to build correctly in the time available, fully within your control (no facilitator, no third-party signing flow), and it's explicitly listed as satisfying the bonus on its own.

**Build: a minimal `Commitment` contract, deployed to Base Sepolia, called once per approved handoff.**

## 18.2 The contract

`contracts/Commitment.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract Commitment {
    event StateCommitted(address indexed committer, bytes32 indexed commitmentHash, uint256 timestamp, string label);

    mapping(bytes32 => uint256) public committedAt;

    function commit(bytes32 commitmentHash, string calldata label) external {
        require(committedAt[commitmentHash] == 0, "already committed");
        committedAt[commitmentHash] = block.timestamp;
        emit StateCommitted(msg.sender, commitmentHash, block.timestamp, label);
    }

    function verify(bytes32 commitmentHash) external view returns (bool exists, uint256 timestamp) {
        uint256 t = committedAt[commitmentHash];
        return (t != 0, t);
    }
}
```

Deploy with Foundry:

```bash
cd contracts
forge init --no-git .   # if not already a Foundry project
forge build

forge create Commitment \
  --rpc-url https://sepolia.base.org \
  --private-key $BASE_PRIVATE_KEY \
  --broadcast
```

Copy the deployed address into `.env` as `BASE_COMMITMENT_CONTRACT_ADDRESS`. Confirm it on `https://sepolia.basescan.org/address/<address>` — this Basescan link is what you'll show on screen during the demo.

## 18.3 Python client

`memora/integrity/commitment.py`:

```python
import hashlib
import json


def canonical_commitment_payload(patient_id: str, situation: str, approved_claims: list[dict]) -> dict:
    """The exact, sorted, minimal representation that gets hashed. No patient
    data beyond synthetic identifiers and claim text ever leaves this
    function's scope — nothing here goes onchain, only its hash."""
    return {
        "patient_id": patient_id,
        "situation": situation,
        "claims": sorted(
            [{"text": c["text"], "gate_result": c["gate_result"]} for c in approved_claims],
            key=lambda c: c["text"],
        ),
    }


def compute_commitment_hash(payload: dict) -> bytes:
    canonical = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).digest()
```

`memora/integrity/base_client.py`:

```python
from web3 import Web3
from eth_account import Account
from memora.config import settings

COMMITMENT_ABI = [
    {
        "inputs": [
            {"name": "commitmentHash", "type": "bytes32"},
            {"name": "label", "type": "string"},
        ],
        "name": "commit",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "commitmentHash", "type": "bytes32"}],
        "name": "verify",
        "outputs": [{"name": "exists", "type": "bool"}, {"name": "timestamp", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def get_web3() -> Web3:
    return Web3(Web3.HTTPProvider(settings.base_rpc_url))


def commit_hash(commitment_hash: bytes, label: str) -> str:
    """Returns the transaction hash — this string, and the resulting
    Basescan link, is what gets shown on screen during the demo."""
    w3 = get_web3()
    account = Account.from_key(settings.base_private_key)
    contract = w3.eth.contract(address=settings.base_commitment_contract_address, abi=COMMITMENT_ABI)

    tx = contract.functions.commit(commitment_hash, label).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 100_000,
        "gasPrice": w3.eth.gas_price,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex()


def verify_hash(commitment_hash: bytes) -> tuple[bool, int]:
    w3 = get_web3()
    contract = w3.eth.contract(address=settings.base_commitment_contract_address, abi=COMMITMENT_ABI)
    exists, timestamp = contract.functions.verify(commitment_hash).call()
    return exists, timestamp
```

Add one more route to `memora/api/routes.py`:

```python
from memora.integrity.commitment import canonical_commitment_payload, compute_commitment_hash
from memora.integrity.base_client import commit_hash


@router.post("/handoff/{patient_id}/approve")
def approve_handoff(patient_id: str, situation: str, approved_claims: list[dict]):
    payload = canonical_commitment_payload(patient_id, situation, approved_claims)
    commitment_hash = compute_commitment_hash(payload)
    tx_hash = commit_hash(commitment_hash, label=f"{patient_id}:{situation}")
    return {
        "commitment_hash": commitment_hash.hex(),
        "tx_hash": tx_hash,
        "basescan_url": f"https://sepolia.basescan.org/tx/{tx_hash}",
    }
```

This is the exact endpoint whose response you screenshot for the demo's integrity-verification beat — real tx hash, real Basescan link, no patient data in the payload beyond synthetic identifiers.


---

# 19. Phase 16 — Fresh-Session Proof Mechanics

This phase exists because the rule is exact: *"A fresh session recalls state written earlier, as one continuous unedited segment with an on-screen timestamp or commit hash."* Get the mechanics right before demo day, not during it.

## 19.1 What "fresh session" must mean here

Sibyl is local-first — *"Everything is local; nothing round-trips to a server"* (README §0.1). That means a fresh session is **not** just calling a function twice in the same running Python process. It has to be a genuinely new OS process re-opening the same on-disk `memory.db`. Two scripts, run separately, on camera:

`scripts/session1.py`:

```python
"""SESSION 1 — writes patient history, then the process exits completely."""

from pathlib import Path
from memora.ingest.pipeline import ingest_patient

print("=== SESSION 1: writing patient history to Sibyl ===")
result = ingest_patient(Path("vendor/synthea/output/fhir/Patient_story_1.json"))
print(f"Ingested: {result}")
print("=== SESSION 1 TERMINATING ===")
# process exits here — no server kept running, no shared Python state
```

`scripts/session2.py`:

```python
"""SESSION 2 — a genuinely new process, run separately, minutes or days
later. It imports nothing from session1.py's run and shares no in-memory
state — the only thing connecting them is the same memory.db file on disk."""

import time
from memora.context.engine import compile_plan, execute_plan
from memora.context.situations import Situation, ClinicianRole

print(f"=== SESSION 2 starting at {time.strftime('%Y-%m-%d %H:%M:%S')} — no prior conversation, fresh process ===")

plan = compile_plan(patient_id="story-patient-1", situation=Situation.ICU_TO_WARD, role=ClinicianRole.WARD_PHYSICIAN)
result = execute_plan(plan)

print(f"Recalled from Sibyl (written in a previous, now-dead process): {result}")
```

## 19.2 Recording the demo segment

Run, on camera, as two separate terminal invocations with the terminal's own visible clock or `date` command bracketing them:

```bash
date && python scripts/session1.py
# ... let the process fully exit, screen still recording, no cuts ...
date && python scripts/session2.py
```

The `date` calls satisfy *"on-screen timestamp"* without needing anything fancier. If you'd rather anchor to a commit hash instead (arguably stronger, since it's independently checkable after the fact, not just a screen timestamp that could theoretically be faked with OS clock tricks), run the Base commitment call (Phase 15) as the very last step of Session 2 and let the Basescan URL be the on-screen proof — a real, independently-verifiable, timestamped record that only exists because Session 2 successfully recalled Session 1's data and got clinician approval on it.

## 19.3 What NOT to do

- Don't record this in two separate takes and edit them together — the rule says *"one continuous unedited segment."*
- Don't run Session 2 inside the same terminal tab without actually letting Session 1's Python process exit — a background process still holding an open SQLite handle undercuts the "fresh" claim if a technical judge asks about it.
- Don't pre-load Session 2's answer or cache it anywhere — see the deletion test in Phase 17, which exists specifically to catch this.


---

# 20. Phase 17 — Testing

## 20.1 Unit tests — Gate logic (no Sibyl required, pure function tests)

`tests/unit/test_gate.py`:

```python
from memora.gate.gate import evaluate_claim, GateResult
from memora.evidence.resolver import EvidenceCheck
from memora.context.situations import ClinicianRole


def test_unsupported_claim_blocks(mocker):
    memory = mocker.Mock()
    evidence = EvidenceCheck(claim_text="Drug A is safe", supported=False, reason="no source")
    decision = evaluate_claim(memory, evidence, ClinicianRole.WARD_PHYSICIAN)
    assert decision.result == GateResult.BLOCK


def test_unauthorized_role_blocks(mocker):
    memory = mocker.Mock()
    memory.get_fact.return_value = {"status": "active"}
    evidence = EvidenceCheck(claim_text="Lab trend rising", supported=True, source_kind="lab_trend", source_name="creatinine")
    decision = evaluate_claim(memory, evidence, ClinicianRole.SURGEON)  # surgeons can't view lab_trend per authority.py
    assert decision.result == GateResult.BLOCK


def test_contraindicated_medication_needs_review(mocker):
    memory = mocker.Mock()
    memory.get_fact.return_value = {"status": "contraindicated"}
    evidence = EvidenceCheck(claim_text="Drug A could be used", supported=True, source_kind="medication", source_name="drug_a")
    decision = evaluate_claim(memory, evidence, ClinicianRole.WARD_PHYSICIAN)
    assert decision.result == GateResult.NEEDS_REVIEW


def test_supported_authorized_no_policy_conflict_allows(mocker):
    memory = mocker.Mock()
    memory.get_fact.return_value = {"status": "active"}
    evidence = EvidenceCheck(claim_text="Patient on Drug B", supported=True, source_kind="medication", source_name="drug_b")
    decision = evaluate_claim(memory, evidence, ClinicianRole.WARD_PHYSICIAN)
    assert decision.result == GateResult.ALLOW
```

## 20.2 Unit tests — Change detector

`tests/unit/test_change_detector.py`:

```python
from memora.ingest.change_detector import apply_fact_change
from memora.ontology.events import ClinicalEvent


def test_new_fact_writes_once(mocker):
    memory = mocker.Mock()
    memory.get_fact.return_value = None
    event = ClinicalEvent(event_type="medication_administered", summary="Drug A started", timestamp="2026-01-01")
    result = apply_fact_change(memory, "medication", "drug_a", {"status": "active"}, event)
    assert result == "new"
    memory.set_fact.assert_called_once()
    memory.log_event.assert_called_once()


def test_identical_fact_is_confirmed_not_rewritten(mocker):
    memory = mocker.Mock()
    memory.get_fact.return_value = {"status": "active"}
    event = ClinicalEvent(event_type="medication_administered", summary="still active", timestamp="2026-01-02")
    result = apply_fact_change(memory, "medication", "drug_a", {"status": "active"}, event)
    assert result == "confirmed"
    memory.set_fact.assert_not_called()  # no redundant write


def test_changed_fact_logs_transition_before_overwrite(mocker):
    memory = mocker.Mock()
    memory.get_fact.return_value = {"status": "active"}
    event = ClinicalEvent(event_type="medication_discontinued", summary="Drug A discontinued", timestamp="2026-01-05")
    result = apply_fact_change(memory, "medication", "drug_a", {"status": "discontinued"}, event)
    assert result == "changed"
    memory.log_event.assert_called_once()
    memory.set_fact.assert_called_once_with("medication", "drug_a", {"status": "discontinued"})
```

## 20.3 Integration tests — real Sibyl, not mocks

`tests/integration/test_sibyl_roundtrip.py`:

```python
import pytest
from memora.sibyl.client import PatientMemory

pytestmark = pytest.mark.integration  # run with: pytest -m integration, requires `sibyl init` already done


def test_fact_roundtrip():
    memory = PatientMemory(patient_id="itest-patient")
    memory.set_fact("medication", "test_drug", {"status": "active"})
    result = memory.get_fact("medication", "test_drug")
    assert result["status"] == "active"


def test_event_roundtrip():
    memory = PatientMemory(patient_id="itest-patient")
    memory.log_event("Integration test event", event_type="test")
    history = memory.read_history()
    assert len(history) >= 1


def test_archive_not_delete():
    memory = PatientMemory(patient_id="itest-patient")
    memory.set_fact("medication", "archive_test", {"status": "active"})
    memory.archive_fact("medication", "archive_test")
    hits = memory.search("archive_test")
    assert not any("archive_test" in str(h) for h in hits)  # gone from active search
    # the file itself should NOT have shrunk to reflect a hard delete —
    # check DB size didn't drop, confirming this was archive not delete
```

## 20.4 The compliance test — automated deletion test

This is the single most important test in the whole suite, because it's a direct, automated version of the actual gate criterion a judge will check by hand.

`tests/compliance/test_deletion.py`:

```python
"""
Directly automates the hackathon's own litmus test: 'delete the Sibyl Memory
layer. Does the project still do what it claims? If yes, it is not
load-bearing, and it is disqualified.'

Run this before every submission, not just once during development —
re-verify after any refactor that touches the repository layer.
"""

import shutil
import pytest
from pathlib import Path
from memora.config import settings
from memora.sibyl.errors import SibylUnavailableError
from memora.context.engine import compile_plan, execute_plan
from memora.context.situations import Situation, ClinicianRole


def test_app_cannot_answer_without_sibyl(tmp_path):
    real_db = settings.sibyl_db_path
    backup = tmp_path / "memory.db.backup"
    shutil.copy(real_db, backup)

    try:
        real_db.unlink()  # simulate "delete the Sibyl Memory layer"

        plan = compile_plan(patient_id="story-patient-1", situation=Situation.ICU_TO_WARD, role=ClinicianRole.WARD_PHYSICIAN)

        with pytest.raises(SibylUnavailableError):
            execute_plan(plan)
        # If this does NOT raise — if the app somehow still returns an
        # answer — that is a failing build, not a passing test. Fix the
        # code path that let it through before touching anything else.

    finally:
        shutil.copy(backup, real_db)  # restore for the rest of the suite
```

## 20.5 Per-phase test checklist

```text
Phase 1  — verify_sibyl.py runs clean, tenant question resolved and recorded
Phase 5  — repository layer round-trips for all five tiers, quota check triggers correctly
Phase 7  — synthea_parser produces >=1 event per resource type tested, chronologically sorted
Phase 8  — change_detector: new/confirmed/changed all covered, ingest_demo.py stays under quota
Phase 9  — compile_plan is deterministic (same inputs -> same RetrievalPlan, assert equality in a test)
Phase 10 — resolve_claim correctly rejects claims with no related_kind/related_name
Phase 11 — all four gate tests in §20.1 pass
Phase 14 — /handoff returns 503 (not a fabricated answer) when Sibyl is unreachable
Phase 15 — commit tx appears on Base Sepolia Basescan, verify() returns (true, timestamp) after
Phase 16 — session1.py / session2.py run as genuinely separate processes, session2 recalls session1's data
Phase 17 — the deletion test (§20.4) passes
```


---

# 21. Phase 18 — Demo Script & Build Order

## 21.1 Demo script (2-5 minute window, per the actual rule)

```text
0:00  Problem: a receiving clinician inherits a patient with days of history
      and no time to read the full chart. Who has this problem: any care
      transition — this hackathon's flagship is ICU -> ward.

0:20  Show story patient P-story-1's accumulated history (a few key COLD
      events: Drug A administered -> adverse reaction -> discontinued).

0:45  SESSION 1: run session1.py on screen, watch it write to Sibyl, watch
      the process terminate. State clearly: "this process is now dead."

1:00  [continuous, unedited from here] SESSION 2: fresh terminal, fresh
      process, `date` on screen, run session2.py. It has no memory of
      Session 1 except what Sibyl persisted.

1:30  Show the /handoff response: claims, each with gate_result and source
      evidence. Point at one ALLOW and one NEEDS_REVIEW/BLOCK explicitly —
      this is the moment that proves the gate isn't decorative.

2:00  Change the situation to PRE_OPERATIVE for the same patient, same
      Sibyl memory. Show that a DIFFERENT subset of facts surfaces. This is
      the actual innovation claim, demonstrated, not asserted.

2:30  Approve the ICU->ward handoff, call /handoff/{id}/approve, show the
      real Base Sepolia tx hash and Basescan link on screen.

2:50  Close: "if we delete Sibyl, this breaks" — show the deletion test
      passing (or a live version of it) as the final proof point.
```

## 21.2 Build order (Sep 1-10)

```text
Day 1  Phase 0-1: environment, sibyl init, verify_sibyl.py fully green,
       tenant question resolved and written down, quota baseline recorded.
Day 2  Phase 2-6: skeleton, config, patient-key strategy, repository layer,
       ontology. Round-trip a hand-written fake patient through all five
       tiers before touching Synthea.
Day 3  Phase 7-8: Synthea generation, FHIR parsing, ingestion pipeline,
       change detector. Pick and ingest your 3-8 story patients, watch the
       quota gauge the whole time.
Day 4  Phase 9-10: Context Engine + Evidence Resolver. Get ICU_TO_WARD
       working end to end for one story patient — this is the CORE
       VERTICAL SLICE, the same discipline as any other build: one
       operation fully correct before adding the rest.
Day 5  Phase 11-13: Gate, clinician roles, LLM proposal layer. Run the
       full unit test suite from Phase 17 §20.1-20.2.
Day 6  Phase 14: API layer wired end to end. Add PRE_OPERATIVE and
       DISCHARGE situations now that ICU_TO_WARD proves the pattern.
Day 7  Phase 15: Base contract deployed to Sepolia, commitment flow tested
       for real, tx hash confirmed on Basescan.
Day 8  Phase 16-17: fresh-session mechanics rehearsed exactly as it'll be
       filmed, deletion test passing, full integration suite green.
Day 9  Record the actual demo video per §21.1, exactly as rehearsed, one
       continuous take. Write the README (Phase 19 checklist below).
Day 10 Buffer day. Submit early — the rules don't accept late entries for
       any reason short of an announced extension. Confirm the repo is
       public, the license file is present, and every link in the
       submission form actually opens before you submit it.
```

---

# 22. Phase 19 — Submission Compliance Checklist (verified against the real rules)

```text
[ ] Public GitHub repo, MIT or Apache-2.0 license file present (not open-ended — these two specifically)
[ ] Repo has real commit history starting on/after Sep 1, 2026
[ ] README states plainly: synthetic patient data only, not for clinical use,
    prototype not HIPAA/compliance-certified
[ ] README's Prior Work declaration present (§0.5 draft, adjust as needed)
[ ] README points to exactly where memory is written and read
    (a judge should find memora/sibyl/client.py in under two minutes)
[ ] README explains which partner stacks are used and where (Base — always;
    Virtuals — only if you actually built and exercised something real)
[ ] Demo video: 2-5 minutes, covers problem/audience, product, how it works,
    how Sibyl Memory is used
[ ] Demo video includes the cold-start recall beat as ONE CONTINUOUS
    UNEDITED SEGMENT with an on-screen timestamp or commit hash
[ ] Demo video published (YouTube unlisted is fine, must be watchable
    without requesting access)
[ ] Two public posts made: the demo video + at least one build-log,
    both tagging @sibylcap and any claimed partner (Base / Virtuals)
[ ] Automated deletion test (Phase 17 §20.4) passes on the exact commit
    you're submitting — re-run it after your final commit, not just once
    earlier in the build
[ ] Base bonus: real deployed contract, real tx hash, shown in the demo
    video itself, not just described
[ ] PMF bonus: budgeted at zero unless you genuinely have a publicly
    verifiable artifact (waitlist, pilot, design partner) — do not
    fabricate one, the rules call this out as disqualifying "including
    after payout"
[ ] Team registered (Aug 16-31 window) before the build window opened
```

---

# 23. Final Definition of Done

```text
[ ] sibyl init / status / health all pass, quota baseline understood
[ ] tenant_id question resolved empirically, not assumed — recorded in
    schema/sibyl-verified-facts.md
[ ] repository layer (Phase 5) has zero silent-fallback paths — every
    Sibyl failure propagates, none are caught-and-defaulted
[ ] 3-8 story patients ingested via Synthea, DB comfortably under the
    2 MiB free-tier cap with margin for the demo's live writes
[ ] change detector correctly distinguishes new / confirmed / changed,
    every "changed" case logs a COLD event before the WARM overwrite
[ ] Context Engine's compile_plan is a pure, deterministic function
    (tested: same inputs -> identical plan)
[ ] Evidence Resolver rejects any claim without a related_kind/related_name
[ ] Deterministic Gate: evidence check, policy check, authority check, all
    three independently tested, no path to ALLOW without a real evidence check
[ ] LLM proposal layer fails closed (empty claims list) on any parse error
[ ] /handoff returns a clean 503 when Sibyl is unreachable, never a
    fabricated answer
[ ] Base commitment contract deployed to Sepolia, verify() round-trips
    correctly after commit()
[ ] Fresh-session demo mechanics rehearsed exactly as they'll be filmed —
    two genuinely separate processes, one continuous unedited recording
[ ] Automated deletion test passes on the final submitted commit
[ ] README, license, Prior Work declaration, and both public posts all
    complete per Phase 19's checklist
[ ] Submission form filled out and triple-checked before the Sep 10,
    11:59 PM PT deadline — links opened yourself, not assumed correct
```

---

*This document supersedes every earlier MEMORA planning doc on any point where they disagree. Every Sibyl Memory and hackathon-rule claim here was checked against `docs.sibyllabs.org` and `hack.sibyllabs.org/rules`, fetched on the day this was written — not carried forward from an earlier draft without re-verification.*
