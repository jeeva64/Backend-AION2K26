from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.repositories_sqla import (
    AdminRepositorySqla,
    CollegeRepositorySqla,
    EventRegistrationRepositorySqla,
    PaymentRepositorySqla,
    UserRepositorySqla,
)


def get_user_repo(session: Annotated[AsyncSession, Depends(get_db)]) -> UserRepositorySqla:
    return UserRepositorySqla(session)


def get_admin_repo(session: Annotated[AsyncSession, Depends(get_db)]) -> AdminRepositorySqla:
    return AdminRepositorySqla(session)


def get_college_repo(session: Annotated[AsyncSession, Depends(get_db)]) -> CollegeRepositorySqla:
    return CollegeRepositorySqla(session)


def get_event_regs_repo(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> EventRegistrationRepositorySqla:
    return EventRegistrationRepositorySqla(session)


def get_payment_repo(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentRepositorySqla:
    return PaymentRepositorySqla(session)
