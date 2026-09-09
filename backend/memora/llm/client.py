"""OpenAI-compatible client pool, pointed at whatever provider .env names.

Groq is the configured provider. Verified against the live account: the
endpoint is OpenAI-compatible, honours response_format={"type":"json_object"},
and serves openai/gpt-oss-120b at 131k context.

One caveat learned by hitting it: Groq sits behind Cloudflare, which rejects
requests carrying a default Python urllib User-Agent with "error code: 1010".
The openai SDK (httpx) is fine. Do not hand-roll HTTP calls to this endpoint.

WHY A POOL. Groq's free tier allows 8,000 tokens per minute, and /compare
issues three handoffs in parallel -- one per situation -- so a single key is
asked for roughly three times its per-minute budget in the same second and the
third request 429s. Rotating across keys spreads those concurrent calls, and
failing over on a 429 means one exhausted key degrades throughput instead of
failing the request.

IMPORTANT: Groq meters per ACCOUNT, not per key. Several keys minted from the
same account share one budget and rotating between them buys nothing. The pool
is only worth configuring with keys from separate accounts.
"""

import itertools
import logging
import threading
from functools import lru_cache

from openai import APIError, APIStatusError, OpenAI, RateLimitError

from memora.config import settings
from memora.llm.errors import LLMUnavailableError

log = logging.getLogger(__name__)


def _keys() -> list[str]:
    """Every configured key, in order, deduped and with blanks dropped.

    LLM_API_KEY stays the single source of truth for the one-key case, so an
    existing .env keeps working untouched; LLM_API_KEYS only adds to it.
    """
    raw = [settings.llm_api_key, *settings.llm_api_keys]
    seen: list[str] = []
    for k in raw:
        k = (k or "").strip()
        if k and k not in seen:
            seen.append(k)
    return seen


@lru_cache(maxsize=1)
def _pool() -> tuple[tuple[OpenAI, ...], "itertools.cycle[int]", threading.Lock]:
    keys = _keys()
    if not keys:
        raise LLMUnavailableError(
            "LLM_API_KEY is not set. MEMORA will not silently skip the proposal "
            "step -- set the key or call the pipeline without the LLM stage."
        )
    if not settings.llm_model:
        raise LLMUnavailableError("LLM_MODEL is not set.")

    clients = tuple(
        OpenAI(base_url=settings.llm_base_url, api_key=k) for k in keys
    )
    log.info("LLM pool: %d key%s configured", len(clients),
             "" if len(clients) == 1 else "s")
    return clients, itertools.cycle(range(len(clients))), threading.Lock()


def key_count() -> int:
    """How many distinct keys are in play. Surfaced by /health."""
    return len(_keys())


def get_client() -> OpenAI:
    """One client from the pool, round-robin.

    itertools.cycle is not thread-safe on its own and FastAPI runs sync route
    handlers in a threadpool, so the advance is taken under a lock. Without it
    two concurrent /compare calls can read the same index and defeat the whole
    point of rotating.
    """
    clients, turn, lock = _pool()
    with lock:
        i = next(turn)
    return clients[i]


def complete(**kwargs):
    """Run a chat completion, moving to the next key when one is rate-limited.

    Every key is tried at most once. A 429 on the last remaining key is
    reported as LLMUnavailableError like any other provider failure -- the
    pipeline never silently proceeds without a proposal, because a handover
    brief missing its claims is worse than one that failed loudly.
    """
    clients, turn, lock = _pool()
    attempts = len(clients)
    last: Exception | None = None

    for n in range(attempts):
        with lock:
            i = next(turn)
        try:
            return clients[i].chat.completions.create(**kwargs)
        except RateLimitError as e:
            last = e
            log.warning("LLM key %d/%d rate-limited%s", i + 1, attempts,
                        "; trying the next key" if n + 1 < attempts else "")
            continue
        except APIStatusError as e:
            # 429 can also surface as a plain status error depending on how the
            # provider frames it; treat it the same way rather than failing a
            # request a spare key could have served.
            if e.status_code == 429 and n + 1 < attempts:
                last = e
                log.warning("LLM key %d/%d returned 429; trying the next key",
                            i + 1, attempts)
                continue
            raise
        except APIError:
            raise

    raise LLMUnavailableError(
        f"All {attempts} LLM key{'' if attempts == 1 else 's'} are rate-limited. "
        f"Groq's free tier allows 8,000 tokens per minute per ACCOUNT, so extra "
        f"keys only help when they come from different accounts. Last error: {last}"
    )
