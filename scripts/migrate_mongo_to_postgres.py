"""Migrate data from the legacy MongoDB database to PostgreSQL.

Usage:
    .venv\\Scripts\\python scripts\\migrate_mongo_to_postgres.py
    .venv\\Scripts\\python scripts\\migrate_mongo_to_postgres.py --force   # wipe target first
    .venv\\Scripts\\python scripts\\migrate_mongo_to_postgres.py --dry-run  # report only

Pipeline (per collection):
  1. connect to Mongo + Postgres, verify target is empty (unless --force)
  2. ensure reference data (event_slots, events)
  3. colleges -> colleges
  4. admins   -> admins
  5. users    -> users
  6. eventregistrations -> event_registrations (mostly validated)

Rejects/issue rows are recorded in `scripts/migration_report_<ts>.json`
and printed as a summary. Mongo data is **never** modified.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

# Make the local app package importable when run as a script.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pymongo import MongoClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.config.settings import settings
from app.db.sqlalchemy import create_engine
from app.models_sqla.admin import Admin
from app.models_sqla.college import College
from app.models_sqla.event import Event, EventSlot
from app.models_sqla.event_registration import EventRegistration
from app.models_sqla.user import User
from app.utils.constants import DEPARTMENTS, EVENT_SLOT_MAP

REPORT_DIR = ROOT / "scripts"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class Report:
    def __init__(self) -> None:
        self.tables: dict[str, dict[str, Any]] = {}
        self.now = dt.datetime.now(dt.timezone.utc).isoformat()

    def init(self, table: str) -> None:
        self.tables.setdefault(
            table,
            {"accepted": 0, "rejected": [], "skipped_duplicate": 0, "skipped": []},
        )

    def accept(self, table: str, n: int = 1) -> None:
        self.init(table)
        self.tables[table]["accepted"] += n

    def reject(self, table: str, record: dict, reason: str) -> None:
        self.init(table)
        self.tables[table]["rejected"].append({"reason": reason, "record": record})

    def skip_dup(self, table: str) -> None:
        self.init(table)
        self.tables[table]["skipped_duplicate"] += 1

    def skip(self, table: str, record: dict, reason: str) -> None:
        self.init(table)
        self.tables[table]["skipped"].append({"reason": reason, "record": record})

    def as_dict(self) -> dict:
        return {"generated_at": self.now, "tables": self.tables}

    def write(self) -> Path:
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = REPORT_DIR / f"migration_report_{ts}.json"
        path.write_text(json.dumps(self.as_dict(), default=str, indent=2), encoding="utf-8")
        return path

    def summary(self) -> str:
        lines = ["Migration report:"]
        for t, d in self.tables.items():
            lines.append(
                f"  {t}: accepted={d['accepted']} "
                f"rejected={len(d['rejected'])} "
                f"skipped_dup={d['skipped_duplicate']} "
                f"skipped={len(d['skipped'])}"
            )
        return "\n".join(lines)


def _clean_mobile(value: Any) -> str:
    if value is None:
        return ""
    import re
    return re.sub(r"\D", "", str(value))


def _is_bcrypt(h: str | None) -> bool:
    return bool(h) and isinstance(h, str) and (h.startswith("$2a$") or h.startswith("$2b$") or h.startswith("$2y$"))


# --------------------------------------------------------------------------- #
# Stages
# --------------------------------------------------------------------------- #
async def _ensure_reference_data(conn) -> None:
    """Idempotent seeding of event_slots + events (mirrors seed_reference_data.py)."""
    slots = [("1", "Slot 1"), ("2", "Slot 2"), ("BOTH", "Bid Mayhem occupies both slots")]
    for label, desc in slots:
        existing = await conn.execute(select(EventSlot).where(EventSlot.slot_label == label))
        if existing.scalars().first() is None:
            await conn.execute(
                EventSlot.__table__.insert().values(slot_label=label, description=desc)
            )

    for name, slot_label in EVENT_SLOT_MAP.items():
        existing = await conn.execute(select(Event).where(Event.name == name))
        if existing.scalars().first() is None:
            slot_id = (
                await conn.execute(select(EventSlot.id).where(EventSlot.slot_label == slot_label))
            ).scalar_one()
            await conn.execute(
                Event.__table__.insert().values(name=name, display_name=name, slot_id=slot_id)
            )


async def _wipe_target(conn) -> None:
    """Truncate all application tables (order respects FKs)."""
    await conn.execute(text("TRUNCATE event_registrations, users, admins, colleges, events, event_slots RESTART IDENTITY CASCADE"))


async def migrate_colleges(conn, mongo_db, report: Report) -> None:
    rows = list(mongo_db["colleges"].find({}))
    seen_ids: set[str] = set()
    for r in rows:
        college_id = r.get("collegeId")
        name = r.get("name")
        if not college_id or not name:
            report.reject("colleges", r, "missing collegeId or name")
            continue
        if college_id in seen_ids:
            report.skip_dup("colleges")
            continue
        seen_ids.add(college_id)
        try:
            await conn.execute(
                College.__table__.insert().values(
                    college_id=college_id,
                    name=name,
                    state=r.get("state") or "",
                    district=r.get("district") or "",
                    registered_status=bool(r.get("registeredStatus", False)),
                )
            )
            report.accept("colleges")
        except IntegrityError:
            report.skip_dup("colleges")


async def migrate_admins(conn, mongo_db, report: Report) -> None:
    rows = list(mongo_db["admins"].find({}))
    seen: set[str] = set()
    for r in rows:
        admin_id = r.get("adminId")
        if not admin_id or not r.get("name") or r.get("role") is None or not r.get("password"):
            report.reject("admins", r, "missing required fields")
            continue
        if admin_id in seen:
            report.skip_dup("admins")
            continue
        seen.add(admin_id)
        if not _is_bcrypt(r.get("password")):
            report.reject("admins", r, f"password is not a bcrypt hash (got prefix: {str(r.get('password'))[:4]!r})")
            continue
        if r["role"] not in (1, 2):
            report.reject("admins", r, f"role out of range (1,2): {r['role']}")
            continue
        try:
            await conn.execute(
                Admin.__table__.insert().values(
                    admin_id=admin_id,
                    name=r["name"],
                    role=int(r["role"]),
                    password_hash=r["password"],
                )
            )
            report.accept("admins")
        except IntegrityError:
            report.skip_dup("admins")


async def migrate_users(conn, mongo_db, report: Report) -> None:
    # Pre-load colleges for FK resolution by exact name match.
    college_ids: dict[str, int] = {
        name: cid
        for cid, name in (
            await conn.execute(select(College.id, College.name))
        ).all()
    }

    rows = list(mongo_db["users"].find({}))
    seen_user: set[str] = set()
    seen_email: set[str] = set()
    seen_mobile: set[str] = set()

    for r in rows:
        userid = r.get("userid")
        if not userid:
            report.reject("users", r, "missing userid")
            continue
        if userid in seen_user:
            report.skip_dup("users")
            continue

        email = (r.get("email") or "").strip().lower()
        mobile = _clean_mobile(r.get("mobilenumber"))
        if not email:
            report.reject("users", r, "missing email")
            continue
        if email in seen_email:
            report.skip_dup("users")
            continue
        if not mobile:
            report.reject("users", r, "missing mobile_number")
            continue
        if mobile in seen_mobile:
            report.skip_dup("users")
            continue
        if not _is_bcrypt(r.get("password")):
            report.reject("users", r, "password not a bcrypt hash")
            continue
        if r.get("department") not in DEPARTMENTS:
            report.reject("users", r, f"bad department: {r.get('department')!r}")
            continue
        if r.get("shift") not in ("1", "2"):
            report.reject("users", r, f"bad shift: {r.get('shift')!r}")
            continue

        college_text = (r.get("college") or "").strip()
        if not college_text:
            report.reject("users", r, "missing college_name_text")
            continue
        college_id = college_ids.get(college_text)  # may be None

        try:
            await conn.execute(
                User.__table__.insert().values(
                    user_id=userid,
                    name=r.get("name") or "",
                    email=email,
                    mobile_number=mobile,
                    department=r["department"],
                    college_name_text=college_text,
                    college_id=college_id,
                    shift=r["shift"],
                    password_hash=r["password"],
                )
            )
            seen_user.add(userid)
            seen_email.add(email)
            seen_mobile.add(mobile)
            report.accept("users")
            if college_id is None:
                report.skip("users", r, "unmatched college_name_text (preserved, college_id=NULL)")
        except IntegrityError:
            report.skip_dup("users")


async def migrate_event_registrations(conn, mongo_db, report: Report) -> None:
    event_ids: dict[str, int] = {
        name: eid
        for eid, name in (await conn.execute(select(Event.id, Event.name))).all()
    }
    slot_ids: dict[str, int] = {
        label: sid
        for sid, label in (await conn.execute(select(EventSlot.id, EventSlot.slot_label))).all()
    }
    user_ids: set[str] = {
        uid for (uid,) in (await conn.execute(select(User.user_id))).all()
    }
    college_ids: dict[str, int] = {
        name: cid for cid, name in (await conn.execute(select(College.id, College.name))).all()
    }

    rows = list(mongo_db["eventregistrations"].find({}))
    seen_keys: set[tuple[str, str]] = set()

    for r in rows:
        leader_id = r.get("leaderId")
        reg_num = (r.get("registerNumber") or "").upper()
        if not leader_id or not reg_num:
            report.reject("event_registrations", r, "missing leaderId or registerNumber")
            continue
        key = (leader_id, reg_num)
        if key in seen_keys:
            report.skip_dup("event_registrations")
            continue
        if leader_id not in user_ids:
            report.reject("event_registrations", r, f"orphan leaderId: {leader_id}")
            continue
        if r.get("department") not in DEPARTMENTS:
            report.reject("event_registrations", r, f"bad department: {r.get('department')!r}")
            continue
        if r.get("degree") not in ("ug", "pg"):
            report.reject("event_registrations", r, f"bad degree: {r.get('degree')!r}")
            continue
        if r.get("foodPreference") not in ("vegetarian", "non-vegetarian"):
            report.reject("event_registrations", r, f"bad foodPreference: {r.get('foodPreference')!r}")
            continue
        event1_name = r.get("event1")
        if event1_name not in EVENT_SLOT_MAP:
            report.reject("event_registrations", r, f"bad event1: {event1_name!r}")
            continue
        event2_name = r.get("event2")
        slot1_label = EVENT_SLOT_MAP[event1_name]
        slot1_id = slot_ids[slot1_label]
        event1_id = event_ids[event1_name]

        event2_id = None
        slot2_id = None
        if event2_name is not None:
            if event2_name not in EVENT_SLOT_MAP:
                report.reject("event_registrations", r, f"bad event2: {event2_name!r}")
                continue
            event2_id = event_ids[event2_name]
            slot2_label = EVENT_SLOT_MAP[event2_name]
            slot2_id = slot_ids[slot2_label]
            if slot1_label == slot2_label:
                report.reject("event_registrations", r, f"same-slot clash: {slot1_label}")
                continue
            if event1_name == event2_name:
                report.reject("event_registrations", r, "event1_id == event2_id")
                continue
        else:
            if r.get("slot2") is not None:
                report.reject("event_registrations", r, "event2 NULL but slot2 not NULL")
                continue
        # Bid Mayhem exclusivity check
        if ("Bid Mayhem" in (event1_name, event2_name or "")) and event2_id is not None:
            report.reject("event_registrations", r, "Bid Mayhem exclusivity violation")
            continue

        college_text = r.get("college") or ""
        if not college_text:
            report.reject("event_registrations", r, "missing college_name_text")
            continue
        college_id = college_ids.get(college_text)

        try:
            await conn.execute(
                EventRegistration.__table__.insert().values(
                    leader_id=leader_id,
                    name=r.get("name") or "",
                    register_number=reg_num,
                    mobile=r.get("mobile") or "",
                    college_name_text=college_text,
                    college_id=college_id,
                    department=r["department"],
                    degree=r["degree"],
                    food_preference=r["foodPreference"],
                    event1_id=event1_id,
                    slot1_id=slot1_id,
                    event2_id=event2_id,
                    slot2_id=slot2_id,
                )
            )
            seen_keys.add(key)
            report.accept("event_registrations")
            if college_id is None:
                report.skip("event_registrations", r, "unmatched college (preserved, college_id=NULL)")
        except IntegrityError as exc:
            report.reject("event_registrations", r, f"integrity: {exc.orig}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
async def run(force: bool, dry_run: bool) -> Report:
    if not settings.MONGO_URI:
        raise SystemExit("MONGO_URI must be set to read the MongoDB source.")

    settings.validate_secrets()
    mongo = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    mongo_db = mongo[settings.MONGO_DB] if settings.MONGO_DB else mongo.get_default_database()
    mongo.admin.command("ping")

    engine = create_engine()
    report = Report()
    try:
        async with engine.begin() as conn:
            if force:
                await _wipe_target(conn)
            # Quick precheck: refuse to run if target tables are non-empty.
            existing_users = int((await conn.execute(text("SELECT count(*) FROM users"))).scalar_one())
            if existing_users > 0 and not force:
                raise SystemExit(
                    "Target Postgres already has data. Use --force to truncate first, "
                    "or point at a fresh database."
                )

            await _ensure_reference_data(conn)
            await migrate_colleges(conn, mongo_db, report)
            await migrate_admins(conn, mongo_db, report)
            await migrate_users(conn, mongo_db, report)
            await migrate_event_registrations(conn, mongo_db, report)

            if dry_run:
                raise RuntimeError("dry-run requested; rolling back")
    except RuntimeError:
        # Dry-run rollback deliberately aborts the outer begin() transaction.
        pass
    finally:
        await engine.dispose()
        mongo.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="truncate target tables before migrating")
    parser.add_argument("--dry-run", action="store_true", help="do not commit; report only")
    args = parser.parse_args()

    report = asyncio.run(run(force=args.force, dry_run=args.dry_run))
    path = report.write()
    print(report.summary())
    print(f"Full report written to: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
