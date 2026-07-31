from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db as get_db

__all__ = ["get_db"]
