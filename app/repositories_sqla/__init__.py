from app.repositories_sqla.admin_repository import AdminRepositorySqla
from app.repositories_sqla.college_repository import CollegeRepositorySqla
from app.repositories_sqla.event_registration_repository import (
    EventRegistrationRepositorySqla,
)
from app.repositories_sqla.payment_repository import PaymentRepositorySqla
from app.repositories_sqla.user_repository import UserRepositorySqla

__all__ = [
    "AdminRepositorySqla",
    "CollegeRepositorySqla",
    "EventRegistrationRepositorySqla",
    "PaymentRepositorySqla",
    "UserRepositorySqla",
]
