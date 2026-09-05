# Phase F10 — Making Sentinel an agent that acts

**Status:** done · backend + frontend

---

## Why this phase existed

Austin asked the sharpest question of the build: **do we actually have an
agent?**

The eligibility gate says:

> *"Your agent must recall and use persisted context in a fresh session. Thin
> wrappers, decorative integrations, and package imports without real execution
> are not eligible."*

Honest audit before this phase:

```
Sentinel  reads : load_digest · list_facts · check_drift
          writes: save_digest
          trigger: a POST — no scheduler
          LLM: none
```

That is an agent loop structurally — perceive → decide → act → remember → next
cycle differs. But two things were weak:

1. **Nothing ran on its own.** Every sweep was a human clicking a button.
2. **It only reported.** It wrote a digest and returned findings; it never
   touched the patient record. An agent that observes and files a note is a
   monitor.

Both are now closed.

---

## 1. The agent acts without being asked

`POST /patients/{id}/events` now triggers a sweep for that patient as part of
the write. **New information entering memory is the trigger** — nobody asks for
the check.

The response carries what the agent did:

```json
"autonomous_check": {
  "ran": true, "records_checked": 64,
  "findings": [ … ], "actions_taken": [ … ]
}
```

A failing check **must not cost a clinical record**. The event is already
durably written, so a sweep that throws is caught, logged, and reported as
`ran: false` — a degraded agent, not a lost record.
`test_the_event_survives_a_failing_autonomous_check` pins that.

---

## 2. The agent takes a real action

`memora/sentinel/actions.py`. When a finding **escalates** — unresolved across
enough checks — Sentinel writes into the patient's own journal:

```
2026-09-05  [critical]  Flagged for review by Sentinel: medication/
                        acetaminophen_325_mg_oral_tablet has conflicted with
                        its own recorded history across 3 checks since
                        2026-09-05.
                        source_id: sentinel-escalation:medication:acetaminophen…
```

**The trigger exists only in memory.** `runs_seen` comes from Sentinel's own
digest. Without that persisted count there is no threshold to cross, so this
action is *unreachable without memory* — which is the eligibility gate stated
precisely: persisted context changing what the agent **does**.

It is idempotent by `source_id`. An agent that repeats itself is noise, and the
record is the thing being protected.
`test_escalation_is_written_only_once` pins that.

The escalation lands in the journal, so it appears on the memory page and feeds
the next handoff. The agent's action becomes memory that shapes the next
decision — the loop closes.

---

## Verified live

```
recording a reaction to: diphenhydramine_hydrochloride_25_mg_oral_tablet

  event recorded : 18520b81-f31…  memory_version 256
  agent checked  : ran=True  64 records — nobody asked it to
    [ESCALATED] medication/acetaminophen_325_mg_oral_tablet
    [NEW]       medication/diphenhydramine_hydrochloride_25_mg_oral
  actions taken  : escalated_to_patient_record
                   acetaminophen_325_mg_oral_tablet  runs_seen: 3
```

In one write the agent noticed the contradiction it had just received **and**
escalated an older one that had persisted across three checks.

```
278 offline tests (5 new) · cumulative e2e 12/12 · 11 routes
```

---

## A test that was wrong, and what it revealed

`test_a_recorded_reaction_creates_real_drift` began failing. Not a regression —
the autonomous check now notices the contradiction **first**, so a human
sweeping afterwards correctly reports `PERSISTING` rather than `NEW`.

That is better behaviour than the test expected: the finding is announced once,
by whoever saw it first. Reporting `NEW` again would be exactly the alert
fatigue the state machine exists to prevent. The test now asserts the agent saw
it as `NEW` and the later human sweep saw `PERSISTING`.

A second failure was purely my error: the escalation fires on the run that
crosses the threshold and is deliberately never repeated, so asserting on the
*last* run's actions found nothing.

---

## Still human-triggered

A sweep from the Sentinel page is still a button. The autonomy added here is
event-driven — the agent reacts to its environment changing. A scheduler
(periodic sweeps with no trigger at all) is the obvious next step and was left
out deliberately: a background loop in a hackathon backend is a reliability risk
during a live demo, and event-driven autonomy is the more defensible claim
because it is observable.
