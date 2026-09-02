"""The LLM proposal layer.

The model reads what Sibyl returned and proposes claims. It has no authority:
everything it emits goes through the Evidence Resolver and the Gate before it
can be shown as verified. This module's job is to make proposing easy to do
well and impossible to do dangerously.

Two things learned by actually calling the model, which shape the design:

  * It invents record kinds. On the very first live call, gpt-oss-120b returned
    related_kind="adverse_reaction" and qwen returned "event" -- neither is a
    MEMORA kind. The prompt therefore states the closed vocabulary explicitly
    and lists the exact citable (kind, name) pairs, and the resolver still
    rejects what slips through. Both layers, because the prompt is a request
    and the resolver is a guarantee.

  * It is fluent about things it was not given. So the prompt names the failure
    mode directly rather than only asking for good behaviour.

Nothing here filters the model's output. Dropping bad claims before the
resolver sees them would hide exactly what the gate exists to demonstrate: the
model proposes, memory decides.
"""

import json
import logging

from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError

from memora.config import settings
from memora.context.engine import RetrievedContext
from memora.llm.client import get_client
from memora.llm.errors import LLMUnavailableError
from memora.ontology.kinds import ALL_KINDS

log = logging.getLogger("memora.llm")

SYSTEM_PROMPT = f"""You are a clinical context assistant preparing a handover brief.

You are NOT the final authority. Every claim you produce is independently
checked against the source records before a clinician sees it, and any claim
that cannot be traced to a provided record is discarded.

Rules, in order of importance:

1. Every claim MUST cite a record from CITABLE RECORDS below, using its exact
   related_kind and related_name strings, copied verbatim.
2. related_kind MUST be one of exactly these values: {", ".join(ALL_KINDS)}.
   No other value is valid. Do not invent a kind from the event type.
3. Never state anything that is not grounded in the provided facts and history.
   Do not infer, extrapolate, reassure, or fill gaps. If the data does not say
   a patient is stable, do not say it.
4. If nothing relevant was retrieved, return an empty claims list. An empty
   list is a correct and useful answer. Inventing a plausible-sounding claim is
   the single worst thing you can do here.

Respond with ONLY a JSON object of this exact shape:
{{"claims": [{{"text": str, "related_kind": str, "related_name": str}}]}}"""


# Fields that duplicate other fields or carry no meaning for claim-writing.
_DROP_FROM_PROMPT = frozenset({
    "label",        # prose restatement of the structured fields
    "last_seen",    # superseded by latest_at / the history block
    "series",       # see _compact_details: the summary carries the trend
    "snomed", "rxnorm",  # coding systems the model must not cite from
    "verification", "intent", "allergy_type", "request_status",
})


def _compact_details(body: dict) -> dict:
    """Trim a stored record to what a model needs to write a claim about it.

    Memory keeps everything; the prompt gets the meaning. A lab trend's raw
    five-point series is the most valuable thing in the store for a clinician
    to SEE, and the least useful thing for the model to READ -- direction and
    delta say "creatinine is rising by 0.4" in a fraction of the tokens.

    This is not cosmetic. Groq's free tier allows 8,000 tokens per minute and
    the uncompacted payload measured 8,742, so a rich store made every request
    fail with a 413 until the prompt stopped carrying raw series data.
    """
    if not isinstance(body, dict):
        return {}
    compact = {k: v for k, v in body.items()
               if k not in _DROP_FROM_PROMPT and v is not None and v != []}
    if body.get("series"):
        compact["reading_count"] = body.get("readings")
    return compact


def build_payload(context: RetrievedContext) -> dict:
    """Render retrieved memory into the shape the model is asked to cite from.

    Citable records are listed explicitly as (kind, name) pairs so the model is
    copying strings rather than composing them -- the failure mode observed
    live was composition, not typos.
    """
    citable = []
    facts = []
    for kind, rows in context.facts.items():
        for row in rows:
            citable.append({"related_kind": kind, "related_name": row["name"]})
            facts.append({
                "related_kind": kind,
                "related_name": row["name"],
                "status": row["status"],
                "details": _compact_details(row["body"]),
            })

    history = [
        {
            "when": event.timestamp[:10],
            "event_type": event.event_type,
            "summary": event.summary,
            "severity": event.severity,
            "related_kind": event.related_kind,
            "related_name": event.related_name,
        }
        for event in context.history
    ]

    return {
        "situation": context.plan.situation.value,
        "clinical_task": context.plan.task,
        "citable_records": citable,
        "current_facts": facts,
        "history": history,
    }


def propose_claims(context: RetrievedContext) -> list[dict]:
    """Ask the model for claims. Returns raw, unfiltered proposals.

    Raises LLMUnavailableError if the provider cannot be reached -- an
    infrastructure fault must not masquerade as "nothing to report".
    Returns [] if the model replies with something unparseable.
    """
    payload = build_payload(context)

    if not payload["citable_records"] and not payload["history"]:
        # Nothing was retrieved. Asking the model to summarise an empty record
        # set is an invitation to invent one, so don't ask.
        log.info("no retrieved records for %s; skipping proposal",
                 context.plan.patient_id)
        return []

    client = get_client()
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",
                 "content": f"RETRIEVED MEMORY:\n{json.dumps(payload, default=str)}"},
            ],
        )
    except (APIConnectionError, APITimeoutError, APIStatusError) as e:
        raise LLMUnavailableError(f"Model provider unreachable: {e}") from e
    except APIError as e:
        raise LLMUnavailableError(f"Model provider error: {e}") from e

    raw = response.choices[0].message.content
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        log.warning("model returned unparseable JSON; proposing nothing")
        return []

    claims = parsed.get("claims") if isinstance(parsed, dict) else None
    if not isinstance(claims, list):
        log.warning("model response had no claims list; proposing nothing")
        return []
    return claims
