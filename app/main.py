import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import admin as admin_api
from app.api import auth as auth_api
from app.config.logging import setup_logging
from app.config.settings import settings
from app.exceptions.api_error import APIError
from app.exceptions import handlers
from app.middleware.cors import add_cors_middleware
from app.middleware.rate_limit import add_rate_limit_middleware, limiter
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.schemas.common import HealthResponse
from app.utils.response import MongoJSONResponse

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.LOG_LEVEL)

    # Primary persistence layer: PostgreSQL via SQLAlchemy.
    from app.db.sqlalchemy import close_db as close_sqla, connect_to_db as connect_sqla

    await connect_sqla()
    logger.info("PostgreSQL connected successfully")

    # Optional legacy MongoDB lifespan (off by default).
    if settings.MONGO_RETAIN and settings.MONGO_URI:
        from app.db.mongo import close_db as close_mongo, connect_to_db as connect_mongo

        await connect_mongo()
        logger.info("MongoDB (legacy, RETAIN=true) connected")

    yield

    await close_sqla()
    if settings.MONGO_RETAIN and settings.MONGO_URI:
        from app.db.mongo import close_db as close_mongo

        await close_mongo()


app = FastAPI(
    title="AION 2K26 Backend",
    version="2.0.0",
    lifespan=lifespan,
    default_response_class=MongoJSONResponse,
)

add_rate_limit_middleware(app)
app.add_middleware(SecurityHeadersMiddleware)
add_cors_middleware(app)
app.add_middleware(RequestLoggingMiddleware)

app.add_exception_handler(APIError, handlers.api_error_handler)
app.add_exception_handler(RequestValidationError, handlers.validation_error_handler)
app.add_exception_handler(StarletteHTTPException, handlers.starlette_http_exception_handler)
app.add_exception_handler(RateLimitExceeded, handlers.rate_limit_exceeded_handler)
app.add_exception_handler(Exception, handlers.unhandled_exception_handler)

app.include_router(auth_api.router, tags=["auth"])
app.include_router(admin_api.router, prefix="/admin", tags=["admin"])


@app.get("/health", response_model=HealthResponse, tags=["health"])
@limiter.exempt
async def health():
    return {"success": True, "message": "Server is running"}
