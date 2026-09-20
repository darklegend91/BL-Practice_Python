"""The structured error contract (guide section 9).

Every failure carries ``code``, ``message``, optional field errors and a
correlation ID. A valid calculation with no suitable candidate is a typed
domain outcome, not an HTTP server failure, so it never reaches here.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.catalog.publication import EditConflict, WorkflowError
from app.collection.adapter import CollectionError
from app.schemas.common import StrictModel
from app.security.authz import Forbidden, NotAuthenticated
from app.security.net_guard import DestinationRefused
from app.services.auth import AuthenticationFailed
from app.services.idempotency import IdempotencyConflict
from app.services.scenarios import NotFound

log = logging.getLogger("llmfit.api")

CORRELATION_HEADER = "X-Correlation-Id"


class FieldError(StrictModel):
    field: str
    message: str


class ErrorBody(StrictModel):
    code: str
    message: str
    correlation_id: str
    field_errors: list[FieldError] = []


def correlation_id(request: Request) -> str:
    existing = getattr(request.state, "correlation_id", None)
    if existing:
        return existing
    generated = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
    request.state.correlation_id = generated
    return generated


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    field_errors: list[FieldError] | None = None,
) -> JSONResponse:
    reference = correlation_id(request)
    body = ErrorBody(
        code=code,
        message=message,
        correlation_id=reference,
        field_errors=field_errors or [],
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={CORRELATION_HEADER: reference},
    )


def _field_errors(exception: RequestValidationError | ValidationError) -> list[FieldError]:
    found: list[FieldError] = []
    for detail in exception.errors():
        location = ".".join(str(part) for part in detail.get("loc", ()) if part != "body")
        found.append(FieldError(field=location or "body", message=detail.get("msg", "invalid")))
    return found


def install(application: FastAPI) -> None:
    @application.exception_handler(RequestValidationError)
    async def _invalid_request(request: Request, exception: RequestValidationError):
        return error_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_request",
            message="The request did not match the expected contract.",
            field_errors=_field_errors(exception),
        )

    @application.exception_handler(ValidationError)
    async def _invalid_domain_value(request: Request, exception: ValidationError):
        return error_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_request",
            message="A supplied value is not valid for this contract.",
            field_errors=_field_errors(exception),
        )

    @application.exception_handler(NotAuthenticated)
    async def _not_authenticated(request: Request, exception: NotAuthenticated):
        return error_response(
            request,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="not_authenticated",
            message="Authentication is required.",
        )

    @application.exception_handler(AuthenticationFailed)
    async def _authentication_failed(request: Request, exception: AuthenticationFailed):
        return error_response(
            request,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="not_authenticated",
            message="Invalid credentials.",
        )

    @application.exception_handler(Forbidden)
    async def _forbidden(request: Request, exception: Forbidden):
        return error_response(
            request,
            status_code=status.HTTP_403_FORBIDDEN,
            code="forbidden",
            message=str(exception),
        )

    @application.exception_handler(NotFound)
    async def _not_found(request: Request, exception: NotFound):
        # Existence is masked across workspaces: not found and not yours look alike.
        return error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message=str(exception),
        )

    @application.exception_handler(EditConflict)
    async def _edit_conflict(request: Request, exception: EditConflict):
        return error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="edit_conflict",
            message=str(exception),
        )

    @application.exception_handler(IdempotencyConflict)
    async def _idempotency_conflict(request: Request, exception: IdempotencyConflict):
        return error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="idempotency_conflict",
            message=str(exception),
        )

    @application.exception_handler(WorkflowError)
    async def _workflow_error(request: Request, exception: WorkflowError):
        return error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="workflow_state",
            message=str(exception),
        )

    @application.exception_handler(DestinationRefused)
    async def _destination_refused(request: Request, exception: DestinationRefused):
        return error_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="destination_refused",
            message=str(exception),
        )

    @application.exception_handler(CollectionError)
    async def _collection_error(request: Request, exception: CollectionError):
        return error_response(
            request,
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="collection_failed",
            message=str(exception),
        )

    @application.exception_handler(Exception)
    async def _unexpected(request: Request, exception: Exception):
        reference = correlation_id(request)
        # The detail goes to the operational log, never to the caller.
        log.exception("unhandled error (correlation_id=%s)", reference)
        return error_response(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="The request could not be completed.",
        )
