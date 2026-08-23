"""registration payment workflow

Revision ID: 0004_registration_payments
Revises: 0003_bid_mayhem_bidirectional
Create Date: 2025-01-01 00:00:03.000000

Additive, non-destructive:
1. event_registrations.status — backfilled 'CONFIRMED' (all pre-payment rows
   are treated as fully registered), then NOT NULL + CHECK + index. No
   server_default is kept, so application code must always set it.
2. payments — one row per leader (UNIQUE leader_id), integer paise money,
   partial UNIQUE index on utr.
3. payment_audit — append-only action history (FK CASCADE to payments).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_registration_payments"
down_revision: Union[str, None] = "0003_bid_mayhem_bidirectional"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- event_registrations.status ---
    op.add_column(
        "event_registrations",
        sa.Column("status", sa.Text(), nullable=True),
    )
    op.execute("UPDATE event_registrations SET status = 'CONFIRMED'")
    op.alter_column("event_registrations", "status", existing_type=sa.Text(), nullable=False)
    op.create_check_constraint(
        "ck_event_registrations_status",
        "event_registrations",
        "status IN ('PAYMENT_PENDING', 'VERIFICATION_PENDING', 'CONFIRMED', 'REJECTED')",
    )
    op.create_index(
        "ix_event_registrations_status", "event_registrations", ["status"]
    )

    # --- payments ---
    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "leader_id",
            sa.Text,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expected_amount_paises", sa.BigInteger, nullable=False),
        sa.Column("submitted_amount_paises", sa.BigInteger, nullable=True),
        sa.Column("currency", sa.Text, nullable=False, server_default="INR"),
        sa.Column("utr", sa.Text, nullable=True),
        sa.Column("payment_status", sa.Text, nullable=False, server_default="PENDING"),
        sa.Column("proof_object_key", sa.Text, nullable=True),
        sa.Column("proof_original_filename", sa.Text, nullable=True),
        sa.Column("proof_mime_type", sa.Text, nullable=True),
        sa.Column("proof_file_size", sa.BigInteger, nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "verified_by",
            sa.Text,
            sa.ForeignKey("admins.admin_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rejection_reason", sa.Text, nullable=True),
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
        sa.CheckConstraint(
            "expected_amount_paises >= 0", name="ck_payments_expected_amount"
        ),
        sa.CheckConstraint(
            "submitted_amount_paises IS NULL OR submitted_amount_paises >= 0",
            name="ck_payments_submitted_amount",
        ),
        sa.CheckConstraint("currency = 'INR'", name="ck_payments_currency"),
        sa.CheckConstraint(
            "payment_status IN ('PENDING', 'VERIFICATION_PENDING', 'SUCCESS', 'REJECTED')",
            name="ck_payments_status",
        ),
    )
    op.create_unique_constraint("uq_payments_leader_id", "payments", ["leader_id"])
    op.create_index(
        "uq_payments_utr",
        "payments",
        ["utr"],
        unique=True,
        postgresql_where=sa.text("utr IS NOT NULL"),
    )
    op.create_index("ix_payments_payment_status", "payments", ["payment_status"])
    op.create_index("ix_payments_submitted_at", "payments", ["submitted_at"])

    # --- payment_audit ---
    op.create_table(
        "payment_audit",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "payment_id",
            sa.BigInteger,
            sa.ForeignKey("payments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("admin_id", sa.Text, nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("old_status", sa.Text, nullable=True),
        sa.Column("new_status", sa.Text, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "action IN ('CREATED', 'PROOF_SUBMITTED', 'VERIFIED', 'REJECTED', 'REOPENED')",
            name="ck_payment_audit_action",
        ),
    )
    op.create_index(
        "ix_payment_audit_payment_created", "payment_audit", ["payment_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("payment_audit")
    op.drop_index("ix_payments_submitted_at", table_name="payments")
    op.drop_index("ix_payments_payment_status", table_name="payments")
    op.drop_index("uq_payments_utr", table_name="payments")
    op.drop_constraint("uq_payments_leader_id", "payments", type_="unique")
    op.drop_table("payments")
    op.drop_index("ix_event_registrations_status", table_name="event_registrations")
    op.drop_constraint(
        "ck_event_registrations_status",
        "event_registrations",
        type_="check",
    )
    op.drop_column("event_registrations", "status")
