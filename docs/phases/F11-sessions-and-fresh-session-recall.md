# F11 — Sessions, threads, and fresh-session recall

**Why this phase exists.** An honest audit against the hackathon's eligibility
gate found we satisfied two of its three bullets and not the third.

| Gate bullet | Before F11 | After |
|---|---|---|
| Critical-path calls a judge can find in 2 minutes | strong | unchanged |
| The deletion test (remove memory, core function breaks) | strong | unchanged |
| **Cold-start recall in a genuinely fresh session** | **weak** | strong |

The existing cold-start beat — delete `memory.db`, watch every route return 503,
restore it — proves **dependence**. It does not prove **recall across a session
boundary**: session A writes, session B recalls, and the decision changes. The
rules list those as separate requirements, and the 40% rubric criterion pays
more for the second one ("recall is competitive; coordination and
dynamic-storage patterns top the band").

## What was rejected, and why

A chat UI with a "New chat" button was considered and rejected. Clearing React
state proves nothing about persistence — it is precisely the "decorative
integration" the rules disqualify by name, and a judge would ask what actually
survived. It also fights MEMORA's own thesis: the question box is deliberately
not a chatbot, because free-form generation is the failure the gate exists to
prevent.

## The design

**Sessions and threads are records in Sibyl, not UI state.** A session is a
clinician working on one patient; it holds threads; a thread holds the
questions asked in it. Both are WARM entities rather than journal events,
because both have lifecycle (`open` → `closed`) and both must be enumerable —
`list_facts(KIND_SESSION)` is a real query.

**The `boot_id` is the load-bearing detail.** `memora/sessions/runtime.py`
generates one UUID fragment at import, therefore exactly once per Python
process. Every session records the boot that created it. So "this recall
crossed a restart" stops being a claim the demo makes and becomes a fact a
judge can check:

```
this process     : 4eede932e3e1
prior sessions   : 5   (5 written by processes that no longer exist)
crossed_restart  : True
```

A client-minted session id could not do this — a browser can mint a new one
with nothing having restarted.

## The loop actually closes

Recording sessions without letting them change anything would be the wrapper
failure. `_influence()` in `routes.py` reports which claims the gate did **not**
simply allow *and* whose cited record is backed by a critical journal entry
written earlier. Merely having prior sessions is not influence.

Measured, across two genuinely separate OS processes:

| | before the earlier session | after, in a fresh process |
|---|---|---|
| "Can I restart naproxen?" | `ALLOW` | **`NEEDS_REVIEW` ×2** |

The response names the changed claims and the recalled event that changed them.
That is persist → recall in a fresh session → **change the decision**, which is
all three of what the judges asked for.

## What was built

**Backend**
- `memora/sessions/runtime.py` — `BOOT_ID`, generated once per process
- `memora/sessions/store.py` — sessions and threads as WARM entities
- `memora/sessions/recall.py` — `prior_context()`, including `crossed_restart`
- 7 routes: `/runtime`, open/list/close sessions, open/list threads,
  `/prior-context`
- `ask` takes an optional `thread_id` and returns `influence`

`thread_id` is optional **by design**: every pre-existing caller and all 303
earlier tests keep working untouched.

**Frontend**
- `components/app/SessionBar.tsx` — session identity, process id, New thread,
  End session, and the recall banner
- `Influence` panel in `AskMemory.tsx` — only rendered when memory actually
  changed the answer; a panel reading "0 prior sessions considered" on every
  answer would be the decoration the rules disqualify
- Session state lives on the patient page so the question box records into the
  open thread and inherits the session's clinician

## Tests

`tests/integration/test_sessions.py` — 14 tests. Thirteen run in-process;
`test_recall_survives_a_real_process_restart` spawns an actual subprocess with
`SIBYL_DB_PATH` in its environment, so nothing it reads could have been
resident in the parent. It asserts the child's `BOOT_ID` differs and that the
parent's session is still found.

**317 passed** (was 303). No regressions.

## Also fixed in this phase

Three defects found while working, all pre-existing:

1. **`CLINICIAN_WALLETS` never worked from `.env`.** pydantic-settings
   JSON-decodes `dict` fields inside the env source *before* validators run, so
   `_parse_wallets` was dead code on that path and the documented
   `dr_arun:0x…` form raised `JSONDecodeError`. It only ever worked when a dict
   was passed directly in Python — which is how the tests exercised it. Fixed
   with `Annotated[dict[str, str], NoDecode]`.

2. **`npm run build` was broken.** `@wagmi/connectors` statically references
   four wallet SDKs that are not installed; `next dev` tolerated it, so it
   never surfaced. Aliased to `false` in `next.config.mjs` — MEMORA configures
   only `injected()`, so installing four wallet SDKs to satisfy imports on dead
   code paths would have been the wrong fix.

3. **A test depended on the developer's `.env`.**
   `test_synthetic_keys_still_work_when_no_wallet_is_registered` asserted
   `registered_wallet("dr_arun") is None`, which held only while
   `CLINICIAN_WALLETS` was unset. Registering a real wallet — the entire point
   of the feature — broke it. Now states the empty registry via a `no_wallets`
   fixture instead of inheriting it from the machine.

## Demo sequence this unlocks

Filmed as one continuous unedited segment:

1. Open a session as Dr. Maya. Note the process id on screen.
2. Document an adverse reaction to an active medication. The autonomous check
   runs unprompted.
3. **Kill the API process on camera.** `curl` it and show the connection fail.
4. Restart it. `git rev-parse --short HEAD` for the on-screen commit hash.
5. Open a session as Dr. Arun. The banner reads *"recall crossed a restart —
   5 prior sessions, 5 written by processes that no longer exist."*
6. Ask the same question. The verdict is `NEEDS_REVIEW`, not `ALLOW`, and the
   panel names the recalled event that changed it.

Step 3 is what makes the rest unarguable.
