"""One error shape for every failure: {"error": {"code": ..., "message": ...}}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.services.analysis import InsufficientData
from app.services.open_meteo import UpstreamError

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def _body(code: str, message: str, **extra) -> dict:
    return {"error": {"code": code, "message": message, **extra}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError):
        return JSONResponse(_body(exc.code, exc.message), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]) or None,
             "message": str(e["msg"]).removeprefix("Value error, ")}
            for e in exc.errors()
        ]
        return JSONResponse(
            _body("VALIDATION_ERROR", details[0]["message"] if details else "Invalid request",
                  details=details),
            status_code=422,
        )

    @app.exception_handler(RateLimitExceeded)
    async def _rate(_: Request, exc: RateLimitExceeded):
        return JSONResponse(_body("RATE_LIMITED", f"Too many requests: {exc.detail}"),
                            status_code=429)

    @app.exception_handler(UpstreamError)
    async def _upstream(_: Request, exc: UpstreamError):
        if exc.rate_limited:
            return JSONResponse(_body("UPSTREAM_RATE_LIMITED", str(exc)), status_code=503,
                                headers={"Retry-After": "60"})
        return JSONResponse(_body("UPSTREAM_TIMEOUT" if exc.timeout else "UPSTREAM_ERROR",
                                  str(exc)), status_code=504 if exc.timeout else 502)

    @app.exception_handler(InsufficientData)
    async def _insufficient(_: Request, exc: InsufficientData):
        return JSONResponse(_body("INSUFFICIENT_DATA", str(exc)), status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled error")
        return JSONResponse(_body("INTERNAL_ERROR", "Something went wrong"), status_code=500)
