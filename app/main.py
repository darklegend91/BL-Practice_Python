"""The HTTP service entry point (guide sections 7 and 9).

The API process serves requests only. Browser work runs in the separate crawler
worker process so it can never block a user request.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app import errors
from app.api import ratelimit
from app.api.v1 import admin, auth, catalog, health, questionnaire, recommendations, scenarios
from app.config import get_settings
from app.errors import CORRELATION_HEADER, error_response
from app.version import APP_VERSION

log = logging.getLogger("llmfit.api")

DESCRIPTION = """
Decides whether to run a downloadable language model on your own hardware or buy
a hosted chat subscription, from structured inputs and a reviewed catalog.

The service performs no model inference and calls no external model API.
"""


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="LLM Fit Advisor",
        version=APP_VERSION,
        description=DESCRIPTION,
        openapi_url="/openapi.json",
    )

    @application.middleware("http")
    async def correlate_and_bound(request: Request, call_next):
        request.state.correlation_id = (
            request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        )
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > settings.max_request_bytes:
            return error_response(
                request,
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                code="request_too_large",
                message=f"The request body exceeds {settings.max_request_bytes} bytes.",
            )
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = request.state.correlation_id
        return response

    application.add_exception_handler(ratelimit.RateLimited, ratelimit.handler)
    errors.install(application)

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(questionnaire.router)
    application.include_router(catalog.router)
    application.include_router(scenarios.router)
    application.include_router(recommendations.router)
    application.include_router(admin.router)
    return application


app = create_app()
