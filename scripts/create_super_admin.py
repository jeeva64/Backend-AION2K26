"""Create the first Super Admin directly in PostgreSQL.

Usage:
    python scripts/create_super_admin.py [<adminId> <name> <password>]

If no CLI args provided, reads from .env:
    INITIAL_ADMIN_ID (default: SA1)
    INITIAL_ADMIN_NAME (default: Root)
    INITIAL_ADMIN_PASSWORD (required)

Requires DATABASE_URL in .env. Safe to re-run - idempotent.
Fails if the adminId already exists.

Legacy Mongo variant preserved as ``scripts/create_super_admin_mongo.py``
for the migration window.
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

from app.auth.security import hash_password
from app.config.settings import settings
from app.db.sqlalchemy import create_engine
from app.models_sqla.admin import Admin


# Load .env file explicitly for os.getenv to work
load_dotenv(Path(__file__).parent.parent / ".env")


def _validate_password(password: str) -> None:
    """Validate password meets leader registration requirements."""
    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must be 8-128 characters")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit")
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        raise ValueError("Password must contain at least one special character")
    if " " in password:
        raise ValueError("Password must not contain spaces")


async def _create(admin_id: str, name: str, password: str) -> int:
    _validate_password(password)
    settings.validate_secrets()
    engine = create_engine()

    try:
        async with engine.begin() as conn:
            existing = await conn.execute(select(Admin).where(Admin.admin_id == admin_id))
            if existing.scalars().first() is not None:
                print(f"Super Admin {admin_id!r} already exists. Skipping creation.")
                return 0

            await conn.execute(
                Admin.__table__.insert().values(
                    admin_id=admin_id,
                    name=name,
                    role=1,
                    password_hash=hash_password(password),
                )
            )
        print(f"Super Admin {admin_id!r} created with role=1.")
        return 0
    finally:
        await engine.dispose()


def main() -> int:
    if len(sys.argv) == 4:
        admin_id, name, password = sys.argv[1], sys.argv[2], sys.argv[3]
    elif len(sys.argv) == 1:
        admin_id = os.getenv("INITIAL_ADMIN_ID", "SA1")
        name = os.getenv("INITIAL_ADMIN_NAME", "Root")
        password = os.getenv("INITIAL_ADMIN_PASSWORD")
        if not password:
            print("Error: INITIAL_ADMIN_PASSWORD not set in .env", file=sys.stderr)
            return 2
    else:
        print(__doc__)
        return 2
    return asyncio.run(_create(admin_id, name, password))


if __name__ == "__main__":
    raise SystemExit(main())
