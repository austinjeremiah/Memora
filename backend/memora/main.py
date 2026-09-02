"""MEMORA API entrypoint.

Every failure mode is translated once, here, so no route can forget to do it.
The mapping is the honest-failure contract:

  503  the Sibyl memory layer is gone or unreadable, or the model provider is
       unreachable. MEMORA refuses rather than answering from nothing. This is
       the response a judge sees when they run the deletion test.
  404  the store is healthy but holds no memory for this patient. A different
       condition from 503, and conflating them would let a deleted memory layer
       masquerade as an ordinary empty patient.
  507  the Sibyl free-tier cap is reached and the write cannot proceed.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from memora.api.routes import router
from memora.config import settings
from memora.llm.errors import LLMUnavailableError
from memora.sibyl.errors import (
    SibylPatientUnknownError,
    SibylQuotaExceededError,
    SibylUnavailableError,
)

logging.basicConfig(level=settings.log_level.upper())

app = FastAPI(
    title="MEMORA",
    version="0.1.0",
    description=(
        "Persistent clinical memory with a deterministic safety gate. "
        "Synthetic patient data only -- not for clinical use."
    ),
)


@app.exception_handler(SibylUnavailableError)
def _sibyl_unavailable(_request: Request, exc: SibylUnavailableError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": "sibyl_unavailable",
                 "detail": f"Cannot reconstruct patient context: {exc}"},
    )


@app.exception_handler(SibylPatientUnknownError)
def _patient_unknown(_request: Request, exc: SibylPatientUnknownError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "patient_unknown", "detail": str(exc)},
    )


@app.exception_handler(SibylQuotaExceededError)
def _quota_exceeded(_request: Request, exc: SibylQuotaExceededError) -> JSONResponse:
    return JSONResponse(
        status_code=507,
        content={"error": "memory_quota_exceeded", "detail": str(exc)},
    )


@app.exception_handler(LLMUnavailableError)
def _llm_unavailable(_request: Request, exc: LLMUnavailableError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": "llm_unavailable", "detail": str(exc)},
    )


app.include_router(router)
