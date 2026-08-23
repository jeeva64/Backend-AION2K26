from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models_sqla.base import Base, TimestampMixin


class EventRegistration(Base, TimestampMixin):
    """One row per registered student. event1/slot1 always set; event2/slot2 nullable."""

    __tablename__ = "event_registrations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    leader_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    register_number: Mapped[str] = mapped_column(Text, nullable=False)
    mobile: Mapped[str] = mapped_column(Text, nullable=False)
    college_name_text: Mapped[str] = mapped_column(Text, nullable=False)
    college_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("colleges.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )
    department: Mapped[str] = mapped_column(Text, nullable=False)
    degree: Mapped[str] = mapped_column(Text, nullable=False)
    food_preference: Mapped[str] = mapped_column(Text, nullable=False)
    event1_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    slot1_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("event_slots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event2_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("events.id", ondelete="RESTRICT"),
        nullable=True,
    )
    slot2_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("event_slots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PAYMENT_PENDING', 'VERIFICATION_PENDING', 'CONFIRMED', 'REJECTED')",
            name="ck_event_registrations_status",
        ),
        CheckConstraint(
            "department IN ('cs', 'it', 'ai', 'ds', 'ca')",
            name="ck_event_registrations_department",
        ),
        CheckConstraint(
            "degree IN ('ug', 'pg')", name="ck_event_registrations_degree"
        ),
        CheckConstraint(
            "food_preference IN ('vegetarian', 'non-vegetarian')",
            name="ck_event_registrations_food_preference",
        ),
        CheckConstraint(
            "(event2_id IS NULL AND slot2_id IS NULL) "
            "OR (event2_id IS NOT NULL AND slot2_id IS NOT NULL)",
            name="ck_event_registrations_event2_slot2_paired",
        ),
        CheckConstraint(
            "event2_id IS NULL OR event1_id <> event2_id",
            name="ck_event_registrations_distinct_events",
        ),
        CheckConstraint(
            "slot2_id IS NULL OR slot1_id <> slot2_id",
            name="ck_event_registrations_no_same_slot_clash",
        ),
        Index(
            "uq_event_registrations_leader_register",
            "leader_id",
            "register_number",
            unique=True,
        ),
        Index("ix_event_registrations_leader_event1", "leader_id", "event1_id"),
        Index("ix_event_registrations_leader_event2", "leader_id", "event2_id"),
        Index(
            "ix_event_registrations_college_dept",
            "college_name_text",
            "department",
        ),
        Index("ix_event_registrations_status", "status"),
        Index("ix_event_registrations_event1", "event1_id"),
        Index("ix_event_registrations_event2", "event2_id"),
    )
