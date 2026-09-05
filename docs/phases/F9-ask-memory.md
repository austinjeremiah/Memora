# Phase F9 — Ask memory a question

**Status:** done · backend (1 endpoint) + frontend

---

## Why this is not a chatbot

A chat invites free-form generation, which is the exact failure the gate exists
to prevent — it would mean building the problem and the solution in the same
feature.

This is a **question box**. It retrieves from memory by keyword, lets the model
propose an answer citing what was found, and puts every claim through the same
Evidence Resolver and the same Gate as a handover brief. A question earns the
model no extra latitude; it only changes how retrieval is scoped.

---

## What is genuinely new

Every other path retrieves by **situation** — a fixed focus table decides what
matters. A question names what the clinician actually wants, so retrieval uses
**Sibyl's FTS5 index**, which nothing else in the app exercises.

`memora/llm/answer.py`:

- `extract_terms()` drops stopwords. A query of only stopwords ("Is it safe?")
  matches everything and therefore nothing useful.
- `search_memory()` searches **each term separately** and merges. A single
  combined query is an implicit AND in FTS5, so "restart drug a" would match
  only records containing every word — usually nothing.
- Matched records bring their journal entries, so an answer can cite *when*
  something happened, not only what is currently true.

---

## The refusal is the point

**If nothing matches, the model is never called.** Inviting it to answer from an
empty result set is precisely how a confident fabrication happens.

And `answered` gates the whole response: if every supporting claim was blocked,
the prose is withheld. An answer whose claims were all refused is a refusal,
not an answer.

---

## Verified live

```
"Are there any documented drug allergies?"
  terms    ['there','documented','drug','allergies']
  matched  5 records
  answered True   verdicts {NEEDS_REVIEW: 1}
  ANSWER   "Yes, there is a documented drug allergy to lisinopril."
    [NEEDS_REVIEW] cites allergy/lisinopril

"What is the amiodarone loading plan?"
  terms    ['amiodarone','loading','plan']
  matched  0 records
  answered False
  answer   ''        ← the model was never asked
  claims   0
```

That second case is the demo beat: a fluent, plausible question that memory
cannot support, and the system says so instead of writing prose.

Backend: 273 offline tests (10 new) + 2 live-LLM. `next build` — 11 routes.

---

## Where it lives

On the patient's memory page, below the header. You are already looking at what
the store holds; the question box asks it something. The panel shows the search
terms, how many records matched, the answer, every supporting claim with its
verdict, and an expandable list of what the search actually found.

---

## Resume

```bash
cd backend && SIBYL_DB_PATH=/path/to/store/memory.db scripts/run_api.sh
cd frontend && npm run dev    # → /app/patients → open one → "Ask this patient's memory"
```
