from typing import Annotated

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.db import get_db
from app.repositories import (
    AdminRepository,
    CollegeRepository,
    EventRegistrationRepository,
    UserRepository,
)


def get_user_repo(db: Annotated[AsyncIOMotorDatabase, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)


def get_admin_repo(db: Annotated[AsyncIOMotorDatabase, Depends(get_db)]) -> AdminRepository:
    return AdminRepository(db)


def get_college_repo(db: Annotated[AsyncIOMotorDatabase, Depends(get_db)]) -> CollegeRepository:
    return CollegeRepository(db)


def get_event_regs_repo(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
) -> EventRegistrationRepository:
    return EventRegistrationRepository(db)
