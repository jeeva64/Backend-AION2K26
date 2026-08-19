"""End-to-end test of the Mongo -> Postgres migration script.

Seeds a scratch MongoDB database with a mix of good and bad records,
runs ``scripts/migrate_mongo_to_postgres.py --force`` against a scratch
Postgres DB, then asserts the report counters match expectations.

Skips itself if no MongoDB is reachable at localhost:27017 (so CI/ devs
without Mongo can still run the rest of the suite).
"""
import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _mongo_available() -> bool:
    try:
        from pymongo import MongoClient
        from pymongo.errors import ServerSelectionTimeoutError

        c = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=1500)
        c.admin.command("ping")
        c.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _mongo_available(), reason="MongoDB not reachable at localhost:27017"
)


def test_migration_report_counters(tmp_path):
    from pymongo import MongoClient

    scratch_db = f"aion_migration_test_{uuid.uuid4().hex[:8]}"
    scratch_pg = f"aion_migration_pg_test_{uuid.uuid4().hex[:8]}"

    # Provision a scratch Postgres DB.
    from sqlalchemy import create_engine
    admin_engine = create_engine(
        "postgresql+psycopg2://aion:aion@localhost:5432/postgres",
        isolation_level="AUTOCOMMIT",
    )
    try:
        with admin_engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text(f'CREATE DATABASE "{scratch_pg}" OWNER aion'))
    finally:
        admin_engine.dispose()

    scratch_dsn = f"postgresql+asyncpg://aion:aion@localhost:5432/{scratch_pg}"
    full_report_path = None
    mongo = MongoClient("mongodb://localhost:27017/")
    db = mongo[scratch_db]
    try:
        # Seed good + bad admins.
        from app.auth.security import hash_password

        db["admins"].insert_many(
            [
                {"adminId": "GOOD1", "name": "G", "role": 1, "password": hash_password("pw")},
                {"adminId": "GOOD1", "name": "dup", "role": 2, "password": hash_password("pw")},  # dup
                {"adminId": "BAD1", "name": "B", "role": 9, "password": hash_password("pw")},  # bad role
                {"adminId": "BAD2", "name": "B", "role": 2, "password": "plaintext"},  # not bcrypt
            ]
        )
        # Seed a good college + a user.
        db["colleges"].insert_one(
            {"collegeId": "C1", "name": "Anna University", "state": "TN", "district": "Chennai", "registeredStatus": False}
        )
        db["users"].insert_one(
            {
                "userid": "LD1",
                "name": "Arjun",
                "email": "ARJUN@example.com",  # should be lowercased
                "mobilenumber": "9876543210",
                "department": "cs",
                "college": "Anna University",
                "shift": "1",
                "password": hash_password("Passw0rd!"),
            }
        )
        # Seed one good event registration and one bad (orphan leader).
        db["eventregistrations"].insert_many(
            [
                {
                    "leaderId": "LD1",
                    "name": "S1",
                    "registerNumber": "ra1",
                    "mobile": "9123456789",
                    "college": "Anna University",
                    "department": "cs",
                    "degree": "ug",
                    "foodPreference": "vegetarian",
                    "event1": "Fixathon",
                    "slot1": "1",
                    "event2": None,
                    "slot2": None,
                },
                {
                    "leaderId": "LD_MISSING",  # orphan — must be rejected
                    "name": "S2",
                    "registerNumber": "ra2",
                    "mobile": "9123456788",
                    "college": "Anna University",
                    "department": "cs",
                    "degree": "ug",
                    "foodPreference": "vegetarian",
                    "event1": "Fixathon",
                    "slot1": "1",
                    "event2": None,
                    "slot2": None,
                },
            ]
        )

        env = os.environ.copy()
        env["MONGO_URI"] = f"mongodb://localhost:27017/{scratch_db}"
        env["DATABASE_URL"] = scratch_dsn
        env["JWT_SECRET"] = "pytest-secret-key-1234567890"

        # Run the migration script as a subprocess so env overrides work.
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "migrate_mongo_to_postgres.py"), "--force"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"migration failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

        # Find the report file written by the script.
        report_glob = sorted((ROOT / "scripts").glob("migration_report_*.json"))
        assert report_glob, f"no migration_report_*.json found. stdout={result.stdout}"
        import json

        report = json.loads(report_glob[-1].read_text(encoding="utf-8"))
        t = report["tables"]

        # Admins: 1 accepted (GOOD1), 1 dup-skip, 2 rejected (bad role, not bcrypt).
        assert t["admins"]["accepted"] == 1, t["admins"]
        assert t["admins"]["skipped_duplicate"] == 1, t["admins"]
        assert len(t["admins"]["rejected"]) == 2, t["admins"]

        # Users: 1 accepted, email lowercased.
        assert t["users"]["accepted"] == 1, t["users"]

        # Event registrations: 1 accepted, 1 rejected (orphan leader).
        assert t["event_registrations"]["accepted"] == 1, t["event_registrations"]
        assert any("orphan" in r["reason"] for r in t["event_registrations"]["rejected"]), (
            t["event_registrations"]["rejected"]
        )

        # Sanity check: email in Postgres is lowercased.
        async def _check_email():
            from sqlalchemy import select
            from sqlalchemy.ext.asyncio import create_async_engine
            from app.models_sqla.user import User

            eng = create_async_engine(scratch_dsn)
            try:
                async with eng.connect() as conn:
                    res = await conn.execute(select(User.email))
                    row = res.first()
                    assert row is not None and row.email == "arjun@example.com"
            finally:
                await eng.dispose()

        asyncio.run(_check_email())
    finally:
        mongo.drop_database(scratch_db)
        # Drop the scratch Postgres DB.
        from sqlalchemy import create_engine, text as satext
        eng2 = create_engine("postgresql+psycopg2://aion:aion@localhost:5432/postgres", isolation_level="AUTOCOMMIT")
        try:
            with eng2.connect() as conn:
                conn.execute(satext(f'DROP DATABASE IF EXISTS "{scratch_pg}" WITH (FORCE)'))
        finally:
            eng2.dispose()
        # Cleanup: remove the report file created during the test.
        for f in (ROOT / "scripts").glob("migration_report_*.json"):
            try:
                f.unlink()
            except OSError:
                pass
