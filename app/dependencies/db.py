"""Database dependency wiring.

By default the app uses PostgreSQL via SQLAlchemy (async). The legacy
MongoDB ``get_db`` helper is renamed to ``get_mongo_db`` and is kept for
the migration window only — it is gated on ``settings.MONGO_RETAIN``.
"""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.sqlalchemy import get_db as _get_sqla_db

# Public AsyncSession dependency used by every SQLA repository factory.
get_db = _get_sqla_db

# Backwards-compatible alias for tests/code that took a session + extra args
AsyncSessionDep = Annotated[AsyncSession, Depends(get_db)]


# Legacy MongoDB access (kept dormant). Only imported on demand to avoid
# pulling Motor into the SQLA-only runtime path.
def get_mongo_db():
    from app.db.mongo import get_db as _get_mongo_db_inner
    return _get_mongo_db_inner()


__all__ = ["get_db", "AsyncSessionDep", "get_mongo_db"]
