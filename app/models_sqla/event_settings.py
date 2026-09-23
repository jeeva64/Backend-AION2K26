from sqlalchemy import BigInteger, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models_sqla.base import Base, TimestampMixin


class EventSettings(Base, TimestampMixin):
    """Singleton row (id = 1) holding global registration settings."""

    __tablename__ = "event_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    registration_deadline = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_event_settings_singleton"),
    )
