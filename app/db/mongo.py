from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config.settings import settings

_client: AsyncIOMotorClient | None = None

# Collection names — MUST match the collections created by the original
# Express/Mongoose backend so the existing data keeps working.
USERS = "users"
ADMINS = "admins"
COLLEGES = "colleges"
EVENTS = "events"
EVENT_REGISTRATIONS = "eventregistrations"


async def connect_to_db() -> AsyncIOMotorDatabase:
    global _client
    settings.validate_secrets()
    _client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    await _client.admin.command("ping")
    return _get_db()


def _get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("MongoDB is not connected. Call connect_to_db first.")
    if settings.MONGO_DB:
        return _client[settings.MONGO_DB]
    return _client.get_default_database()


def get_db() -> AsyncIOMotorDatabase:
    return _get_db()


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
