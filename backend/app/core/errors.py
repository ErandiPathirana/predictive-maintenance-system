"""One error shape for every failure:

    {"error": {"code": "machine_readable", "message": "Plain English.", "details": {...}}}

Internal exceptions and stack traces are logged, never returned.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message, self.details = message, details


class ModelNotReadyError(AppError):
    status_code, code = 503, "model_not_ready"


class InputValidationError(AppError):
    status_code, code = 422, "invalid_sensor_readings"


class CsvValidationError(AppError):
    status_code, code = 422, "invalid_csv"


class UnsupportedFileError(AppError):
    status_code, code = 415, "unsupported_file"


class FileTooLargeError(AppError):
    status_code, code = 413, "file_too_large"


class NotFoundError(AppError):
    status_code, code = 404, "not_found"


class BadQueryError(AppError):
    status_code, code = 422, "invalid_query"


class AuthError(AppError):
    status_code, code = 401, "unauthorized"


class DatabaseUnavailableError(AppError):
    status_code, code = 503, "database_unavailable"


class IdempotencyConflictError(AppError):
    status_code, code = 409, "idempotency_conflict"


class EmailNotConfiguredError(AppError):
    status_code, code = 503, "email_not_configured"


class EmailSendError(AppError):
    status_code, code = 502, "email_failed"


class DuplicateSendError(AppError):
    status_code, code = 409, "duplicate_send"


class RateLimitError(AppError):
    status_code, code = 429, "email_rate_limited"


class WorkflowStateError(AppError):
    status_code, code = 409, "invalid_state"


class MaintenanceInputError(AppError):
    status_code, code = 422, "invalid_maintenance_update"


class PredictionError(AppError):
    status_code, code = 500, "prediction_failed"


def _body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return {"error": err}


def _safety_headers(request: Request) -> dict[str, str]:
    """The security/correlation headers normally added by the request middleware. Responses produced by the outermost
    (500) handler never pass through that middleware, so they must carry the headers themselves."""
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}
    rid = getattr(request.state, "request_id", None)
    if rid:
        headers["X-Request-ID"] = rid
    return headers


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Only the location and the rule are returned, never the submitted value.
        problems = [{"field": ".".join(str(p) for p in e["loc"] if p not in ("body", "query")), "problem": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content=_body("invalid_request", "The request is not in the expected format.", {"problems": problems}))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body("http_error", str(exc.detail)))

    @app.exception_handler(SQLAlchemyError)
    async def _database(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        # Driver messages can contain SQL, parameters (IDs) or connection details, so only the exception TYPES are logged.
        logger.error("Database error %s/%s on %s %s", type(exc).__name__, type(getattr(exc, "orig", None)).__name__, request.method, request.url.path)
        return JSONResponse(status_code=503, headers=_safety_headers(request), content=_body(
            "database_unavailable", "The database could not complete the request, so nothing was changed. Please try again."))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled %s", type(exc).__name__, exc_info=exc)
        return JSONResponse(status_code=500, headers=_safety_headers(request),
                            content=_body("internal_error", "Something went wrong on the server. Please try again."))
