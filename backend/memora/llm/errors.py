"""LLM failure modes.

The distinction here is deliberate:

  LLMUnavailableError  the provider could not be reached, or refused the
                       request. That is an infrastructure fault and must be
                       visible -- it becomes a 503, never an empty brief that
                       reads like "this patient has nothing noteworthy".

  A malformed response is NOT an error. The model returning unparseable JSON
  means it proposed nothing usable, so the proposal layer yields zero claims
  and the pipeline continues honestly with nothing to verify.
"""


class LLMError(Exception):
    """Base for proposal-layer failures."""


class LLMUnavailableError(LLMError):
    """The model provider could not be reached or refused the request."""
