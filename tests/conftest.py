"""Pytest fixtures — PostgreSQL (async SQLAlchemy) backend.

Replaces the MongoDB-based conftest. The session fixture:
  1. Forces RATE_LIMIT_ENABLED=false so slowapi doesn't interfere.
  2. Runs `alembic upgrade head` against the dedicated test DB (aion_pytest_test).
  3. Drops all tables at the start of the run (clean slate) — but uses
     `alembic upgrade head` to provision them, exercising the real migration.
  4. Seeds the bootstrap Super Admin (SA1 / Admin@12345, role=1).
"""
import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://aion:aion@localhost:5432/aion_pytest_test"
)
os.environ.setdefault("JWT_SECRET", "pytest-secret-key-1234567890")
os.environ["RATE_LIMIT_ENABLED"] = "false"
# Mongo should NOT be active during the test run.
os.environ["MONGO_RETAIN"] = "false"
# Payment proofs go to a scratch local dir (no cloud credentials in tests).
os.environ.setdefault("PROOF_STORAGE_BACKEND", "local")
os.environ.setdefault(
    "PROOF_LOCAL_DIR", os.path.join(os.path.expanduser("~"), ".aion_proof_tests")
)

import asyncio
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.auth.security import hash_password
from app.config.settings import settings
from app.main import app

ROOT = Path(__file__).resolve().parent.parent


async def _reset_schema() -> None:
    """Drop everything in the test DB so we get a clean slate before upgrade."""
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            # Drop the Bid Mayhem trigger/function first to avoid locking issues.
            await conn.execute(text("DROP TRIGGER IF EXISTS trg_bid_mayhem ON event_registrations"))
            await conn.execute(text("DROP FUNCTION IF EXISTS enforce_bid_mayhem_exclusivity()"))
            # Drop tables ignoring FK order.
            await conn.execute(
                text(
                    "DROP TABLE IF EXISTS payment_audit, payments, "
                    "event_registrations, users, admins, colleges, events, "
                    "event_slots, alembic_version CASCADE"
                )
            )
    finally:
        await engine.dispose()


def _alembic_upgrade() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head failed (rc={result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


async def _seed_super_admin() -> None:
    from app.models_sqla.admin import Admin

    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                Admin.__table__.insert().values(
                    admin_id="SA1",
                    name="Root",
                    role=1,
                    password_hash=hash_password("Admin@12345"),
                )
            )
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def client():
    asyncio.run(_reset_schema())
    _alembic_upgrade()
    asyncio.run(_seed_super_admin())

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_registrations(client):
    """Per-test cleanup of event_registrations so each test starts fresh.

    Users/admins/colleges persist across tests (set up by tests themselves),
    but registrations are centralised state that grows fast — wiping per test
    avoids cross-test contamination of stats queries.
    """
    yield
    import asyncio as _aio
    import shutil as _shutil

    async def _wipe():
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine as _cae

        eng = _cae(settings.DATABASE_URL)
        try:
            async with eng.begin() as conn:
                await conn.execute(
                    text(
                        "TRUNCATE payment_audit, payments, event_registrations "
                        "RESTART IDENTITY CASCADE"
                    )
                )
        finally:
            await eng.dispose()

    _aio.run(_wipe())

    proof_dir = settings.PROOF_LOCAL_DIR
    if os.path.isdir(proof_dir):
        _shutil.rmtree(proof_dir, ignore_errors=True)
