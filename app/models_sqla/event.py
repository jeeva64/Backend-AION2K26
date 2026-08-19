from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models_sqla.base import Base, TimestampMixin


class EventSlot(Base, TimestampMixin):
    """Reference table: '1', '2', 'BOTH' (Bid Mayhem occupies both slots)."""

    __tablename__ = "event_slots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    slot_label: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "slot_label IN ('1', '2', 'BOTH')", name="ck_event_slots_label"
        ),
    )


class Event(Base, TimestampMixin):
    """Reference table seeded from ``EVENT_SLOT_MAP`` (8 events)."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    slot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("event_slots.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_events_slot_id", "slot_id"),
    )
