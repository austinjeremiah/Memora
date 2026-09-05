"""Answering a clinician's question from memory.

The reactive path so far has been situation-driven: a fixed focus table decides
what to recall. A question is different -- it names what the clinician actually
wants to know, and Sibyl's FTS5 index is the right way to find it.

The architecture is unchanged. Memory is searched, the model proposes an answer
citing what was found, and every claim goes through the same Evidence Resolver
and the same Gate. A question does not earn the model any more latitude; it
only changes how retrieval is scoped.

If nothing matches the question, the model is not asked. Inviting it to answer
from an empty result set is exactly how a confident fabrication happens.
"""

import json
import logging
import re
from dataclasses import dataclass, field

from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError

from memora.config import settings
from memora.llm.client import get_client
from memora.llm.errors import LLMUnavailableError
from memora.ontology.events import ClinicalEvent
from memora.ontology.kinds import ALL_KINDS
from memora.sibyl.client import PatientMemory

log = logging.getLogger("memora.llm")

MAX_MATCHES = 12

# Words that match everything and therefore nothing useful. FTS5 ranks by
# relevance, but a query of only stopwords returns noise.
_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "can", "could",
    "should", "would", "do", "does", "did", "has", "have", "had", "for", "of",
    "to", "in", "on", "at", "and", "or", "but", "if", "this", "that", "these",
    "what", "which", "who", "when", "how", "why", "any", "all", "i", "we",
    "patient", "safe", "ok", "okay",
})


@dataclass
class QuestionContext:
    question: str
    terms: list[str]
    matches: list[dict] = field(default_factory=list)
    events: list[ClinicalEvent] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.matches


def extract_terms(question: str) -> list[str]:
    """Content words to search memory for.

    Deliberately simple. Sibyl's FTS5 tokenizer is porter+unicode61, so it
    already handles stemming -- what matters here is dropping words that would
    match everything.
    """
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]*", question.lower())
    terms = [w for w in words if w not in _STOPWORDS and len(w) > 2]
    return terms[:8]


def search_memory(memory: PatientMemory, question: str) -> QuestionContext:
    """Find records this question is about, using Sibyl's FTS5 index.

    Each term is searched separately and the results merged. A single combined
    query is an implicit AND in FTS5, so "restart drug a" would match only
    records containing every word -- usually nothing.
    """
    terms = extract_terms(question)
    ctx = QuestionContext(question=question, terms=terms)
    if not terms:
        return ctx

    seen: set[tuple[str, str]] = set()
    for term in terms:
        for row in memory.search(term, limit=6):
            key = (row["category"], row["name"])
            if key in seen or row["category"] not in ALL_KINDS:
                continue
            seen.add(key)
            ctx.matches.append(row)
            if len(ctx.matches) >= MAX_MATCHES:
                break
        if len(ctx.matches) >= MAX_MATCHES:
            break

    # The journal entries behind whatever matched, so the answer can cite when
    # things happened rather than only what is currently true.
    from memora.evidence.resolver import _matching_events

    for row in ctx.matches[:6]:
        for ev in _matching_events(memory, row["category"], row["name"]):
            ctx.events.append(ClinicalEvent(
                event_type=ev.event_type, summary=ev.summary,
                timestamp=ev.timestamp, related_kind=row["category"],
                related_name=row["name"], source_id=ev.source_id,
                severity=ev.severity))
    return ctx


SYSTEM_PROMPT = f"""You are answering a clinician's question about one patient,
using ONLY the records retrieved from that patient's memory.

You are NOT the final authority. Every claim you produce is independently
checked against those records before the clinician sees it, and any claim that
cannot be traced to one is discarded.

Rules, in order of importance:

1. Every claim MUST cite a record from MATCHED RECORDS, using its exact
   related_kind and related_name, copied verbatim.
2. related_kind MUST be one of: {", ".join(ALL_KINDS)}. No other value is valid.
3. Answer the question directly. If the records answer it, say so plainly and
   cite them. If they do NOT, say that the records do not answer it -- do not
   reason from clinical knowledge, and do not reassure.
4. A question is not permission to speculate. "There is no record of X" is a
   correct and useful answer; inventing X is the worst thing you can do here.

Respond with ONLY a JSON object:
{{"answer": str, "claims": [{{"text": str, "related_kind": str, "related_name": str}}]}}

`answer` is one or two sentences a clinician reads first. `claims` are the
individual assertions it rests on, each independently checkable."""


def answer_question(ctx: QuestionContext) -> dict:
    """Ask the model. Returns {"answer": str, "claims": [...]}.

    Raises LLMUnavailableError if the provider is unreachable -- an
    infrastructure fault must not look like "the records do not answer this".
    """
    if ctx.is_empty():
        return {"answer": "", "claims": []}

    payload = {
        "question": ctx.question,
        "matched_records": [
            {"related_kind": m["category"], "related_name": m["name"],
             "status": m["status"], "details": _compact(m["body"])}
            for m in ctx.matches
        ],
        "history": [
            {"when": e.timestamp[:10], "event_type": e.event_type,
             "summary": e.summary, "severity": e.severity,
             "related_kind": e.related_kind, "related_name": e.related_name}
            for e in ctx.events[:20]
        ],
    }

    client = get_client()
    try:
        response = client.chat.completions.create(
            model=settings.llm_model, temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",
                 "content": f"QUESTION: {ctx.question}\n\nMATCHED RECORDS:\n"
                            f"{json.dumps(payload, default=str)}"},
            ],
        )
    except (APIConnectionError, APITimeoutError, APIStatusError) as e:
        raise LLMUnavailableError(f"Model provider unreachable: {e}") from e
    except APIError as e:
        raise LLMUnavailableError(f"Model provider error: {e}") from e

    try:
        parsed = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, TypeError):
        log.warning("model returned unparseable JSON for a question")
        return {"answer": "", "claims": []}

    if not isinstance(parsed, dict):
        return {"answer": "", "claims": []}
    claims = parsed.get("claims")
    return {
        "answer": str(parsed.get("answer") or ""),
        "claims": claims if isinstance(claims, list) else [],
    }


_DROP = frozenset({"label", "last_seen", "series", "snomed", "rxnorm",
                   "verification", "intent", "allergy_type"})


def _compact(body: object) -> dict:
    if not isinstance(body, dict):
        return {}
    return {k: v for k, v in body.items()
            if k not in _DROP and v is not None and v != []}
