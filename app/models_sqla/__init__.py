"""Re-export ORM models for convenient imports."""
from app.models_sqla.admin import Admin
from app.models_sqla.base import Base, TimestampMixin
from app.models_sqla.college import College
from app.models_sqla.event import Event, EventSlot
from app.models_sqla.event_registration import EventRegistration
from app.models_sqla.user import User

__all__ = [
    "Admin",
    "Base",
    "College",
    "Event",
    "EventRegistration",
    "EventSlot",
    "TimestampMixin",
    "User",
]
