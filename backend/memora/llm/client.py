"""OpenAI-compatible client, pointed at whatever provider .env names.

Groq is the configured provider. Verified against the live account: the
endpoint is OpenAI-compatible, honours response_format={"type":"json_object"},
and serves openai/gpt-oss-120b at 131k context.

One caveat learned by hitting it: Groq sits behind Cloudflare, which rejects
requests carrying a default Python urllib User-Agent with "error code: 1010".
The openai SDK (httpx) is fine. Do not hand-roll HTTP calls to this endpoint.
"""

from functools import lru_cache

from openai import OpenAI

from memora.config import settings
from memora.llm.errors import LLMUnavailableError


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    if not settings.llm_api_key:
        raise LLMUnavailableError(
            "LLM_API_KEY is not set. MEMORA will not silently skip the proposal "
            "step -- set the key or call the pipeline without the LLM stage."
        )
    if not settings.llm_model:
        raise LLMUnavailableError("LLM_MODEL is not set.")
    return OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
