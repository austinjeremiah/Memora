# Phase F8 — Gate-proof page and polish

**Status:** done · frontend only

---

## `/app/proof` — the criterion, runnable

The hackathon's pass/fail test is:

> *"Delete the Sibyl Memory layer. Does the project still do what it claims?
> If yes, it is not load-bearing, and it is disqualified."*

Until now that was proven in `tests/compliance/test_deletion.py` and in stage 9
of `scripts/e2e_full.sh` — both real, both invisible to anyone not reading the
repo. This page makes it something a judge can run in the browser.

It probes **every** endpoint and separates them into those that need the memory
layer and those that do not:

| Needs memory | Does not |
|---|---|
| `GET /readyz` · `GET /patients` · `GET /patients/{id}/memory` · `POST /handoff` · `POST /sentinel/run` | `GET /health` · `GET /clinicians` |

With memory present, the clinical rows answer. Delete `memory.db`, restart, and
probe again: every clinical row must turn **503 refused**. Not an empty result
that looks like an answer.

The page states the reason the guard exists, because it is the least obvious
thing in the project:

> `MemoryClient.local()` silently **recreates** an empty store when `memory.db`
> is missing — it does not raise. Without a check before the client is ever
> constructed, MEMORA would have answered 200 with an empty brief and failed
> this criterion while every test stayed green.

---

## Polish

`/app/settings` rebuilt on the design system. It now states plainly what the
app holds locally — almost nothing:

- the API base URL, in `localStorage`
- `SITUATIONS`, the one genuinely static list, because no endpoint exposes the
  enum

and why: an earlier version hardcoded a patient id and a quota cap, and **both
went stale**. Patients, clinicians and the quota cap are read from the backend
on every request.

It also carries the honesty labels in one place: synthetic patients only, and
attestation signers are synthetic demo keys or explicitly registered wallets —
neither being a real clinician identity.

---

## Verified

```
cumulative e2e:  12 passed, 0 failed
   stage 9  ✓ MEMORA refused to answer without its memory layer
            ✓ the store was NOT silently recreated
backend:         263 offline tests
next build:      11 routes, clean
tsc --noEmit:    clean
```

---

## The app is now feature-complete for the demo

| Route | Demo beat |
|---|---|
| `/app` | memory is alive, real quota |
| `/app/patients` | real UUIDs, discovered not hardcoded |
| `/app/patients/[id]` | the raw record — facts, trajectories, journal |
| `/app/handoff/new` → `result` | Groq proposes, the gate judges, evidence graphs |
| `/app/compare` | one store, three situations, three answers |
| `/app/sentinel` | memory contradicting itself, announced once |
| `/app/proof` | delete memory, watch it refuse |
| `/app/settings` | what is stored locally, and the honesty labels |

Remaining: **F9** (question box), then README, LICENSE, video, posts.
