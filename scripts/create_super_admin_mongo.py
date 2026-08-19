"""Create the first Super Admin directly in MongoDB (LEGACY — migration window).

Superseded by ``scripts/create_super_admin.py`` which targets PostgreSQL.
Kept temporarily so a MongoDB source can be bootstrapped before the data
migration run.

Usage:
    python scripts/create_super_admin_mongo.py <adminId> <name> <password>

Requires MONGO_URI (and optionally MONGO_DB) in .env.
"""
import sys

from pymongo import MongoClient

from app.auth.security import hash_password
from app.config.settings import settings


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2

    admin_id, name, password = sys.argv[1], sys.argv[2], sys.argv[3]
    if not settings.MONGO_URI:
        print("MONGO_URI not set; this legacy script needs a Mongo source.")
        return 2

    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[settings.MONGO_DB] if settings.MONGO_DB else client.get_default_database()

    if db["admins"].find_one({"adminId": admin_id}):
        print(f"Admin {admin_id!r} already exists. Aborting.")
        client.close()
        return 1

    db["admins"].insert_one(
        {"adminId": admin_id, "name": name, "role": 1, "password": hash_password(password)}
    )
    print(f"Super Admin {admin_id!r} created with role=1 (MongoDB source).")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
