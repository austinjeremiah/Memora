# Phase F4 + F5 — Handoff flow, evidence graph, compare

**Status:** done · frontend only

F5 was pulled forward into the same work: deleting the shared `claimDisplay.tsx`
broke `compare`, and patching it minimally stripped import lines that happened
to match the regex. Rebuilding it properly was cleaner than repairing a
half-broken file.

---

## The evidence graph — `components/app/EvidenceGraph.tsx`

Provenance for **one claim**, drawn:

```
 ● medication/drug_a  [contraindicated]
 │
 ├─● medication_administered   2024-06-16   a6869a41-21c4…
 ├─● adverse_reaction ⚠        2026-01-04   fhir-air-7
 └─● medication_discontinued   2026-01-04   fhir-med-9
 ┊
 ● NEEDS REVIEW
```

**Why this and not a knowledge graph.** The whole-patient graph was measured
before deciding: 253 of 253 journal events cite a record, so a graph exists —
but it is bipartite and shallow, max degree 6, and the top of the distribution
is all repeated vitals. Drawn wholesale it would be a hairball proving nothing,
and the rules are blunt that *"clever but useless caps out low"*.

Also checked: Sibyl has an `entity_relations` table (`from_id`, `to_id`,
`relation_type`) but **no SDK method exposes it**. Using it would mean raw SQL
past the repository facade and past the cap gate, and claiming "we use Sibyl's
graph" would be overclaiming. Left alone.

Plain inline SVG. A chart library for a five-node tree would be all cost.

---

## `ClaimCard`

The verdict never appears alone:

- **BLOCK** → the reason it was refused
- **ALLOW / NEEDS_REVIEW** → the cited record, its status, triggered rules, and
  an expandable evidence graph

One deliberate behaviour: `ALLOW` claims are pre-selected for approval,
**`NEEDS_REVIEW` are not**. A flagged claim should require a deliberate click
rather than arriving pre-approved.

---

## Pages rebuilt

`handoff/new` · `handoff/result` · `compare` — all on the F1 design system.

`BackendGate` was also rewritten. It now distinguishes two different failures
that had been collapsed together:

- **nothing answered** → wrong API URL, or the server is not running
- **Sibyl unavailable** → the backend answered and said its memory is gone

The second is surfaced by pages as a 503 with an explanation; the first has
nothing to explain, so the gate replaces the page and offers Settings.

---

## Verified against live data

```
POST /handoff  →  model: openai/gpt-oss-120b   proposed: 24
                  verdicts: {ALLOW: 22, NEEDS_REVIEW: 1, BLOCK: 1}
                  23/24 claims carry source events

BLOCKED: "Full-time employment (finding) active"
         "No current fact and no recorded event support this claim."
```

That block is a good demo moment: the model proposed something plausible from
a Synthea social-history record, and the gate refused it outright.

`next build` — 9 routes, clean. `tsc --noEmit` — clean.

---

## Note for the demo

This patient's claims are mostly routine medications, so the NEEDS_REVIEW
exists but the story is thin. Before filming, run all three patients and pick
whichever produces the sharpest contrast.

---

## Resume

```bash
cd backend && SIBYL_DB_PATH=/path/to/store/memory.db scripts/run_api.sh
cd frontend && npm run dev     # → /app/handoff/new
```
