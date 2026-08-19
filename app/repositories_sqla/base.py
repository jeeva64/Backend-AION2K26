"""Generic async SQLAlchemy repository helpers returning plain dicts.

Domain repositories build on these helpers so the service/router layer keeps
the same call shape it had under Motor (``dict`` in/out). Repos return
``dict``; columns use snake_case, exactly mirroring what Mongo ``find_*``
returned once BSON types were sanitized.
"""
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession


def _row_to_dict(row: Any) -> dict:
    """Convert a SQLAlchemy row to a plain dict (handles ORM + Mapping row)."""
    obj = getattr(row, "tuple", None)
    if obj is not None:
        # Row-like (e.g. ChunkedCursor result); convert via tuple + keys mapping
        try:
            mapping = row._mapping  # SQLAlchemy exposes .mapping on Row objects
        except AttributeError:
            mapping = None
        if mapping is not None:
            return {k: _scalar(v) for k, v in mapping.items()}
    if hasattr(row, "__table__"):
        return {c.name: _scalar(getattr(row, c.name)) for c in row.__table__.columns}
    return dict(row)


def _scalar(value: Any) -> Any:
    """JSON-safe coercion (datetime stays as datetime; downstream serializer handles)."""
    return value


async def scalars_all(session: AsyncSession, stmt: Select) -> list:
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mappings_all(session: AsyncSession, stmt: Select) -> list[dict]:
    result = await session.execute(stmt)
    return [dict(row) for row in result.mappings().all()]


async def mapping_one(session: AsyncSession, stmt: Select) -> dict | None:
    result = await session.execute(stmt)
    row = result.mappings().first()
    return dict(row) if row else None


async def scalar_one(session: AsyncSession, stmt: Select) -> Any:
    result = await session.execute(stmt)
    return result.scalar_one()
