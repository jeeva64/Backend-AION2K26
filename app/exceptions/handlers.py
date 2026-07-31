import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions.api_error import APIError
from app.utils.response import MongoJSONResponse

logger = logging.getLogger("app")


async def api_error_handler(request: Request, exc: APIError):
    return MongoJSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message},
    )


async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = ".".join(str(part) for part in first.get("loc", []) if part != "body")
    message = f"{loc}: {first.get('msg', 'Invalid request')}" if loc else first.get("msg", "Invalid request")
    return MongoJSONResponse(
        status_code=400,
        content={"success": False, "message": message, "errors": errors},
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return MongoJSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": str(exc.detail)},
    )


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return MongoJSONResponse(
        status_code=429,
        content={"success": False, "message": "Too many requests. Please try again later."},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return MongoJSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error"},
    )
