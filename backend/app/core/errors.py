"""One error shape for every failure:

    {"error": {"code": "machine_readable", "message": "Plain English.", "details": {...}}}

Internal exceptions and stack traces are logged, never returned.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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


class PredictionError(AppError):
    status_code, code = 500, "prediction_failed"


def _body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return {"error": err}


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

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled %s", type(exc).__name__, exc_info=exc)
        return JSONResponse(status_code=500, content=_body("internal_error", "Something went wrong on the server. Please try again."))
