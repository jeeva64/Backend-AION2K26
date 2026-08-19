"""Verify PostgreSQL CHECK/FK/UNIQUE constraints reject invalid data.

These tests bypass the API and exercise the schema directly, confirming
that the rule chain lives in the DB (per Phase 2 design).
"""
import asyncio

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.config.settings import settings
from app.models_sqla.admin import Admin
from app.models_sqla.college import College
from app.models_sqla.event import Event, EventSlot
from app.models_sqla.event_registration import EventRegistration
from app.models_sqla.user import User


async def _conn():
    engine = create_async_engine(settings.DATABASE_URL)
    return engine, engine.connect()


async def _events_map():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            res = await conn.execute(
                "SELECT id, name FROM events" if False else __import__("sqlalchemy").select(Event.id, Event.name)
            )
            return {row.name: row.id for row in res.all()}
    finally:
        await engine.dispose()


async def _slots_map():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            from sqlalchemy import select
            res = await conn.execute(select(EventSlot.id, EventSlot.slot_label))
            return {row.slot_label: row.id for row in res.all()}
    finally:
        await engine.dispose()


def _seed_user(engine, user_id="LD1", email="a@b.co", mobile="9123456789"):
    return engine, User(
        user_id=user_id,
        name="Arjun",
        email=email,
        mobile_number=mobile,
        department="cs",
        college_name_text="Anna",
        shift="1",
        password_hash="$2b$10$abc",
    )


@pytest.mark.asyncio
async def test_admin_role_check_constraint():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(Admin).values(
                        admin_id="X1", name="N", role=3, password_hash="$2b$10$abc"
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_admin_unique_admin_id():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(Admin).values(admin_id="DUP1", name="N1", role=2, password_hash="$2b$10$abc")
            )
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(Admin).values(admin_id="DUP1", name="N2", role=2, password_hash="$2b$10$abc")
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_user_email_unique_case_sensitive_db_constraint():
    """The DB unique constraint on email is case-sensitive, mirroring the
    original Mongo index. Email lowercasing is enforced at the service layer
    before INSERT (see app.api.auth.register_leader). Here we just verify
    the same exact email/string is rejected.
    """
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(User).values(
                    user_id="LDU1", name="U1", email="dup@example.com",
                    mobile_number="9111111111", department="cs",
                    college_name_text="C", shift="1", password_hash="$2b$10$abc",
                )
            )
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(User).values(
                        user_id="LDU2", name="U2", email="dup@example.com",  # same exact case
                        mobile_number="9222222222", department="it",
                        college_name_text="C", shift="2", password_hash="$2b$10$abc",
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_user_bad_department():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(User).values(
                        user_id="LDBD", name="U", email="bd@example.com",
                        mobile_number="9333333333", department="mech",
                        college_name_text="C", shift="1", password_hash="$2b$10$abc",
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_registration_event2_without_slot2():
    events = await _events_map()
    slots = await _slots_map()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(User).values(
                    user_id="LDX1", name="X", email="x@example.com",
                    mobile_number="9444444444", department="cs",
                    college_name_text="C", shift="1", password_hash="$2b$10$abc",
                )
            )
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(EventRegistration).values(
                        leader_id="LDX1", name="S1", register_number="RX1",
                        mobile="9123456789", college_name_text="C", department="cs",
                        degree="ug", food_preference="vegetarian",
                        event1_id=events["Fixathon"], slot1_id=slots["1"],
                        event2_id=events["QRush"],  # slot2_id intentionally omitted
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_registration_same_event_twice():
    events = await _events_map()
    slots = await _slots_map()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(User).values(
                    user_id="LDX2", name="X", email="y@example.com",
                    mobile_number="9555555555", department="cs",
                    college_name_text="C", shift="1", password_hash="$2b$10$abc",
                )
            )
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(EventRegistration).values(
                        leader_id="LDX2", name="S1", register_number="RX2",
                        mobile="9123456789", college_name_text="C", department="cs",
                        degree="ug", food_preference="vegetarian",
                        event1_id=events["Fixathon"], slot1_id=slots["1"],
                        event2_id=events["Fixathon"], slot2_id=slots["1"],  # same event twice
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_registration_same_slot_clash():
    events = await _events_map()
    slots = await _slots_map()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(User).values(
                    user_id="LDX3", name="X", email="z@example.com",
                    mobile_number="9666666666", department="cs",
                    college_name_text="C", shift="1", password_hash="$2b$10$abc",
                )
            )
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(EventRegistration).values(
                        leader_id="LDX3", name="S1", register_number="RX3",
                        mobile="9123456789", college_name_text="C", department="cs",
                        degree="ug", food_preference="vegetarian",
                        event1_id=events["Fixathon"], slot1_id=slots["1"],
                        event2_id=events["Mute Masters"], slot2_id=slots["1"],  # both slot 1
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_registration_bid_mayhem_trigger_blocks_second_event():
    events = await _events_map()
    slots = await _slots_map()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(User).values(
                    user_id="LDX4", name="X", email="w@example.com",
                    mobile_number="9777777777", department="cs",
                    college_name_text="C", shift="1", password_hash="$2b$10$abc",
                )
            )
            # Insert Bid Mayhem as event1 — succeeds.
            await conn.execute(
                insert(EventRegistration).values(
                    leader_id="LDX4", name="S1", register_number="RX4A",
                    mobile="9123456789", college_name_text="C", department="cs",
                    degree="ug", food_preference="vegetarian",
                    event1_id=events["Bid Mayhem"], slot1_id=slots["BOTH"],
                )
            )
            # UPDATE adding a second event → trigger raises. The plpgsql
            # RAISE EXCEPTION surfaces via asyncpg as a generic DBAPIError
            # (not IntegrityError), so we catch the broader base.
            from sqlalchemy import update
            from sqlalchemy.exc import DBAPIError

            with pytest.raises(DBAPIError):
                await conn.execute(
                    update(EventRegistration)
                    .where(EventRegistration.register_number == "RX4A")
                    .values(event2_id=events["QRush"], slot2_id=slots["2"])
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_registration_leader_unique_register():
    events = await _events_map()
    slots = await _slots_map()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(User).values(
                    user_id="LDX5", name="X", email="v@example.com",
                    mobile_number="9888888888", department="cs",
                    college_name_text="C", shift="1", password_hash="$2b$10$abc",
                )
            )
            await conn.execute(
                insert(EventRegistration).values(
                    leader_id="LDX5", name="S1", register_number="RXDUP",
                    mobile="9123456789", college_name_text="C", department="cs",
                    degree="ug", food_preference="vegetarian",
                    event1_id=events["Fixathon"], slot1_id=slots["1"],
                )
            )
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(EventRegistration).values(
                        leader_id="LDX5", name="S2", register_number="RXDUP",
                        mobile="9123456790", college_name_text="C", department="cs",
                        degree="ug", food_preference="vegetarian",
                        event1_id=events["QRush"], slot1_id=slots["2"],
                    )
                )
    finally:
        await engine.dispose()
