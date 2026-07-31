"""Ensure the unique indexes the application relies on exist.

Run once against an existing database:
    python scripts/ensure_indexes.py

Requires MONGO_URI (and optionally MONGO_DB) in .env. Idempotent.
"""

from pymongo import MongoClient

from app.config.settings import settings


def main() -> int:
    settings.validate_secrets()

    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[settings.MONGO_DB] if settings.MONGO_DB else client.get_default_database()

    db["users"].create_index("userid", unique=True)
    db["users"].create_index("email", unique=True)
    db["users"].create_index("mobilenumber", unique=True)

    db["admins"].create_index("adminId", unique=True)
    db["colleges"].create_index("collegeId", unique=True)

    db["eventregistrations"].create_index(
        [("leaderId", 1), ("registerNumber", 1)], unique=True
    )
    db["eventregistrations"].create_index([("leaderId", 1), ("event1", 1)])
    db["eventregistrations"].create_index([("leaderId", 1), ("event2", 1)])

    print("Indexes ensured.")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
