"""event_settings singleton table for registration deadline

Revision ID: 0005_event_settings
Revises: 0004_registration_payments
Create Date: 2025-01-01 00:00:04.000000

Additive, non-destructive:
1. event_settings — singleton row (id=1) holding registration_deadline (TIMESTAMPTZ).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_event_settings"
down_revision: Union[str, None] = "0004_registration_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_settings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("registration_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("id = 1", name="ck_event_settings_singleton"),
    )
    # Seed singleton row
    op.execute("INSERT INTO event_settings (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("event_settings")
