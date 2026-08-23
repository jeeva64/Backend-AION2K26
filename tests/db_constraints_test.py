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
from app.models_sqla.payment import Payment, PaymentAudit
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
                        status="CONFIRMED",
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
                        status="CONFIRMED",
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
                        status="CONFIRMED",
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
            # Insert Bid Mayhem as event1 â€” succeeds.
            await conn.execute(
                insert(EventRegistration).values(
                    leader_id="LDX4", name="S1", register_number="RX4A",
                    mobile="9123456789", college_name_text="C", department="cs",
                    degree="ug", food_preference="vegetarian",
                    status="CONFIRMED",
                    event1_id=events["Bid Mayhem"], slot1_id=slots["BOTH"],
                )
            )
            # UPDATE adding a second event â†’ trigger raises. The plpgsql
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
async def test_registration_bid_mayhem_as_event2_insert_blocked():
    """Bidirectional enforcement (revision 0003): a row whose SECOND event is
    Bid Mayhem must also be rejected by the DB trigger â€” the same-slot CHECK
    does not catch it ('1' <> 'BOTH').
    """
    events = await _events_map()
    slots = await _slots_map()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(User).values(
                    user_id="LDX6", name="X", email="bm2@example.com",
                    mobile_number="9999999991", department="cs",
                    college_name_text="C", shift="1", password_hash="$2b$10$abc",
                )
            )
            from sqlalchemy.exc import DBAPIError

            with pytest.raises(DBAPIError):
                await conn.execute(
                    insert(EventRegistration).values(
                        leader_id="LDX6", name="S1", register_number="RX6",
                        mobile="9123456789", college_name_text="C", department="cs",
                        degree="ug", food_preference="vegetarian",
                        status="CONFIRMED",
                        event1_id=events["Fixathon"], slot1_id=slots["1"],
                        event2_id=events["Bid Mayhem"], slot2_id=slots["BOTH"],
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_registration_bid_mayhem_as_event2_update_blocked():
    """UPDATE path: adding Bid Mayhem as event2 to an existing single-event
    row must be rejected by the trigger.
    """
    events = await _events_map()
    slots = await _slots_map()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(User).values(
                    user_id="LDX7", name="X", email="bm3@example.com",
                    mobile_number="9999999992", department="cs",
                    college_name_text="C", shift="1", password_hash="$2b$10$abc",
                )
            )
            # Single-event row â€” succeeds.
            await conn.execute(
                insert(EventRegistration).values(
                    leader_id="LDX7", name="S1", register_number="RX7A",
                    mobile="9123456789", college_name_text="C", department="cs",
                    degree="ug", food_preference="vegetarian",
                    status="CONFIRMED",
                    event1_id=events["Fixathon"], slot1_id=slots["1"],
                )
            )
            # UPDATE swapping in Bid Mayhem as event2 â†’ trigger raises.
            from sqlalchemy import update
            from sqlalchemy.exc import DBAPIError

            with pytest.raises(DBAPIError):
                await conn.execute(
                    update(EventRegistration)
                    .where(EventRegistration.register_number == "RX7A")
                    .values(event2_id=events["Bid Mayhem"], slot2_id=slots["BOTH"])
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
                    status="CONFIRMED",
                    event1_id=events["Fixathon"], slot1_id=slots["1"],
                )
            )
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(EventRegistration).values(
                        leader_id="LDX5", name="S2", register_number="RXDUP",
                        mobile="9123456790", college_name_text="C", department="cs",
                        degree="ug", food_preference="vegetarian",
                        status="CONFIRMED",
                        event1_id=events["QRush"], slot1_id=slots["2"],
                    )
                )
    finally:
        await engine.dispose()

def _payment_user_values(user_id, email, mobile):
    return dict(
        user_id=user_id, name="P", email=email,
        mobile_number=mobile, department="cs",
        college_name_text="C", shift="1", password_hash="$2b$10$abc",
    )


@pytest.mark.asyncio
async def test_registration_status_check_constraint():
    events = await _events_map()
    slots = await _slots_map()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(User).values(**_payment_user_values("LDS1", "st@example.com", "9711111111"))
            )
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(EventRegistration).values(
                        leader_id="LDS1", name="S", register_number="RS1",
                        mobile="9123456789", college_name_text="C", department="cs",
                        degree="ug", food_preference="vegetarian",
                        status="MAYBE",  # invalid status
                        event1_id=events["Fixathon"], slot1_id=slots["1"],
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_payment_unique_leader_and_fk():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(User).values(**_payment_user_values("LDP1", "pay@example.com", "9722222222"))
            )
        async with engine.begin() as conn:
            await conn.execute(
                insert(Payment).values(leader_id="LDP1", expected_amount_paises=40000)
            )
        # Duplicate leader_id.
        async with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(Payment).values(leader_id="LDP1", expected_amount_paises=100)
                )
        # FK violation on unknown leader.
        async with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(Payment).values(leader_id="LD_NOPE", expected_amount_paises=100)
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_payment_checks_and_partial_unique_utr():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(insert(User).values(**_payment_user_values("LDP2", "pay2@example.com", "9733333333")))
            await conn.execute(insert(User).values(**_payment_user_values("LDP3", "pay3@example.com", "9744444444")))
        async with engine.begin() as conn:
            await conn.execute(
                insert(Payment).values(leader_id="LDP2", expected_amount_paises=40000, utr="UTR12345ABCD")
            )
        # Negative amount.
        async with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(Payment).values(leader_id="LDP2", expected_amount_paises=-5)
                )
        # Bad status.
        async with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(Payment).values(
                        leader_id="LDP3", expected_amount_paises=1, payment_status="WEIRD"
                    )
                )
        # Duplicate UTR across leaders.
        async with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(Payment).values(leader_id="LDP3", expected_amount_paises=1, utr="UTR12345ABCD")
                )
        from sqlalchemy import select as sa_select

        async with engine.begin() as conn:
            await conn.execute(insert(User).values(**_payment_user_values("LDP5", "pay5@example.com", "9766666666")))
            await conn.execute(
                insert(Payment).values(leader_id="LDP3", expected_amount_paises=1)
            )
            await conn.execute(
                insert(Payment).values(leader_id="LDP5", expected_amount_paises=1)
            )
            nulls = (
                await conn.execute(sa_select(Payment.id).where(Payment.utr.is_(None)))
            ).scalars().all()
            assert len(nulls) >= 2  # multiple NULL utrs allowed (partial index)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_payment_audit_cascades_on_payment_delete():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            from sqlalchemy import delete as sa_delete, select as sa_select

            await conn.execute(insert(User).values(**_payment_user_values("LDP4", "pay4@example.com", "9755555555")))
            await conn.execute(
                insert(Payment).values(leader_id="LDP4", expected_amount_paises=20000)
            )
            pid = (await conn.execute(sa_select(Payment.id))).scalar_one()
            await conn.execute(
                insert(PaymentAudit).values(payment_id=pid, action="CREATED", new_status="PENDING")
            )
            assert pid is not None and int(pid) > 0
            await conn.execute(sa_delete(Payment).where(Payment.id == pid))
            remaining = (await conn.execute(sa_select(PaymentAudit))).scalars().all()
            assert remaining == []
    finally:
        await engine.dispose()
