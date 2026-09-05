# MEMORA phase log

One document per build phase, covering **both** backend and frontend. Each
records what shipped, what was decided and why, what broke and how it was
fixed, and exactly what was verified — so a session starting cold can pick up
without re-deriving context.

Planning documents live at the repo root and describe *intent*:
- `Memora.md` — the original v1 build plan (Phases 0–19)
- `memora-v2.md` — Sentinel and Attestation

These describe what was actually built.

## Phases

| Phase | Title | Status |
|---|---|---|
| v1 | Backend Phases 2–15 | done — see `Memora.md` and commit history |
| v2 | Sentinel + Attestation | done — see `memora-v2.md` |
| [B](B-api-additions-for-ui.md) | Backend API additions for the UI | done |
| [F1](F1-design-system-shell.md) | App design system and shell | done |
| [F2+F3](F2-F3-client-and-memory-explorer.md) | Client layer, patients, memory explorer | done |
| [F4+F5](F4-F5-handoff-and-compare.md) | Handoff flow, evidence graph, compare | done |
| [F6](F6-sentinel-and-drift.md) | Sentinel UI, drift graph, record events | done |
| [F7](F7-attestation-and-wallet.md) | Attestation + wallet signing (wagmi) | done |
| F8 | Gate-proof page + polish | next |
| F9 | Question box — FTS search → propose → gate | planned |

## Running everything

```bash
# backend  (port 8000, documented default)
cd backend && scripts/run_api.sh

# frontend (port 3000)
cd frontend && npm run dev

# the full cumulative end-to-end — every stage as a separate OS process,
# real Sibyl, real Groq, real Base Sepolia
cd backend && bash scripts/e2e_full.sh

# tests
cd backend && ./.venv/bin/python -m pytest tests/ -q                      # all
cd backend && ./.venv/bin/python -m pytest tests/ -q -m "not llm and not chain"  # offline
cd backend/contracts && forge test
```
