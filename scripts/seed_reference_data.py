"""Ensure the PostgreSQL reference data (event_slots, events) exists.

Replaces the legacy ``scripts/ensure_indexes.py`` (Mongo). Idempotent —
safe to re-run after schema upgrades. The unique indexes/constraints are
created by Alembic; this script only seeds the reference rows.
"""
import asyncio

from sqlalchemy import select, text

from app.config.settings import settings
from app.db.sqlalchemy import create_engine
from app.models_sqla.event import Event, EventSlot

SLOTS = [
    ("1", "Slot 1 events"),
    ("2", "Slot 2 events"),
    ("BOTH", "Bid Mayhem occupies both slots simultaneously"),
]

EVENTS = [
    ("Fixathon", "Fixathon", "1"),
    ("Mute Masters", "Mute Masters", "1"),
    ("Treasure Titans", "Treasure Titans", "1"),
    ("Bid Mayhem", "Bid Mayhem", "BOTH"),
    ("QRush", "QRush", "2"),
    ("VisionX", "VisionX", "2"),
    ("ThinkSync", "ThinkSync", "2"),
    ("Crazy Sell", "Crazy Sell", "2"),
]


async def _seed() -> None:
    settings.validate_secrets()
    engine = create_engine()
    try:
        async with engine.begin() as conn:
            for label, desc in SLOTS:
                existing = await conn.execute(
                    select(EventSlot).where(EventSlot.slot_label == label)
                )
                if existing.scalars().first() is None:
                    await conn.execute(
                        EventSlot.__table__.insert().values(
                            slot_label=label, description=desc
                        )
                    )
            for name, display, slot_label in EVENTS:
                existing = await conn.execute(select(Event).where(Event.name == name))
                if existing.scalars().first() is None:
                    slot_id = (
                        await conn.execute(
                            select(EventSlot.id).where(EventSlot.slot_label == slot_label)
                        )
                    ).scalar_one()
                    await conn.execute(
                        Event.__table__.insert().values(
                            name=name, display_name=display, slot_id=slot_id
                        )
                    )
        print("Reference data seeded (event_slots, events).")
    finally:
        await engine.dispose()


def main() -> int:
    asyncio.run(_seed())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
