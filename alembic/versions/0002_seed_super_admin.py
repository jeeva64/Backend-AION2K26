"""seed bootstrap super admin (idempotent)

Revision ID: 0002_seed_super_admin
Revises: 0001_initial_schema
Create Date: 2025-01-01 00:00:01.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_super_admin"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op by default. The bootstrap Super Admin must be created explicitly
    # via `scripts/create_super_admin.py SA1 Root "YourPassword"` (which uses
    # bcrypt from app.auth.security) — never hardcode a hash in the migration.
    pass


def downgrade() -> None:
    pass
