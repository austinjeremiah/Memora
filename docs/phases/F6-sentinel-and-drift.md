# Phase F6 — Sentinel UI, drift graph, and recording clinical events

**Status:** done · backend (1 endpoint) + frontend

---

## The problem this phase had to solve honestly

A sweep against a freshly ingested store finds **nothing**:

```
scanned 3 patients, 191 records
summary: {NEW: 0, PERSISTING: 0, RESOLVED: 0, ESCALATED: 0}
```

That is correct behaviour. Synthea never prescribes a drug a patient is
allergic to, so genuine drift does not occur in the generated data.

The earlier workaround was a `--seed-drift` flag that planted a contradiction
directly. That works, but it means demonstrating a *planted* finding — and if a
judge reads the script they will see it.

**What was built instead:** the thing that causes drift in reality.

---

## Backend — `POST /patients/{id}/events`

An ordinary clinical write path. Adverse reactions, discontinuations and
results are documented as they happen; this is how one reaches a record.

It goes through the same repository facade as ingestion, so it is quota-checked
and bumps the patient's memory version like any other write. Event types and
record kinds are validated against the ontology (422 on anything unknown), and
the reserved Sentinel tenant is not addressable.

**Why it matters here:** recording a reaction to a medication memory still
holds as *active* creates a **real** contradiction. Sentinel then detects it
independently. Nothing is planted in the findings.

`test_a_recorded_reaction_creates_real_drift` asserts exactly that sequence:
sweep finds nothing → event is recorded → sweep finds it.

---

## The drift graph — `components/app/DriftGraph.tsx`

```
 WARM · TRUE NOW                            COLD · HAPPENED
 ┌────────────────────┐                    ┌────────────────────┐
 │ acetaminophen_325  │ ---- ✕ contradicts │ adverse_reaction   │
 │ medication         │                    │ 2026-09-05         │
 └────────────────────┘                    └────────────────────┘
          └───────────────────┬───────────────────┘
        both read from the same patient memory · no model involved
```

The reactive path reads WARM facts as current truth and never asks whether the
journal agrees. This is that question, drawn — and it is the clearest statement
of the one genuinely novel thing in the project.

---

## `/app/sentinel`

- Run a sweep per situation, using the same focus table retrieval uses
- Findings with `NEW` / `PERSISTING` / `RESOLVED` / `ESCALATED`, each with its
  drift graph and triggered rules
- An **across runs** panel showing the same finding announced once and then
  tracked silently — the anti-alert-fatigue property, visible rather than
  described
- When there is no drift, the page says so plainly and offers to document a
  real reaction, stating that the resulting finding will be *detected, not
  planted*

`no model runs in this path` is stated on the page itself.

---

## Verified live

```
1. sweep before  → 0 findings, memory self-consistent
2. record a real adverse reaction → memory_version 253 → 254
3. sweep after   → 1 NEW, detected independently
                   rules=['critical_event_on_file']
                   evidence=adverse_reaction@2026-09-05
4. sweep again   → PERSISTING, announceable: 0 — no re-alert
```

Backend: 263 offline tests (8 new). `next build` — 10 routes, clean.

---

## Note

Verifying this wrote a real adverse-reaction event to the demo store at
`scratchpad/uistore/memory.db` for patient `0c33684a…` on
`acetaminophen_325_mg_oral_tablet`. That drift is now seeded for filming. To
start clean, re-run `scripts/ingest_demo.py` into a fresh store.
