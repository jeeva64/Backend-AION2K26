from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import func

from app.models_sqla.base import Base


class Payment(Base):
    """One payment per leader (UNIQUE). Money is integer paise — never floats."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    leader_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    expected_amount_paises: Mapped[int] = mapped_column(BigInteger, nullable=False)
    submitted_amount_paises: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="INR")
    utr: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="PENDING"
    )
    proof_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    submitted_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_by: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("admins.admin_id", ondelete="SET NULL"),
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "expected_amount_paises >= 0",
            name="ck_payments_expected_amount",
        ),
        CheckConstraint(
            "submitted_amount_paises IS NULL OR submitted_amount_paises >= 0",
            name="ck_payments_submitted_amount",
        ),
        CheckConstraint("currency = 'INR'", name="ck_payments_currency"),
        CheckConstraint(
            "payment_status IN ('PENDING', 'VERIFICATION_PENDING', 'SUCCESS', 'REJECTED')",
            name="ck_payments_status",
        ),
        Index("uq_payments_leader_id", "leader_id", unique=True),
        Index(
            "uq_payments_utr",
            "utr",
            unique=True,
            postgresql_where=Text("utr IS NOT NULL"),
        ),
        Index("ix_payments_payment_status", "payment_status"),
        Index("ix_payments_submitted_at", "submitted_at"),
    )


class PaymentAudit(Base):
    """Append-only audit trail for payment actions. Never updated or deleted."""

    __tablename__ = "payment_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
    )
    admin_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    old_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('CREATED', 'PROOF_SUBMITTED', 'VERIFIED', 'REJECTED', 'REOPENED')",
            name="ck_payment_audit_action",
        ),
        Index("ix_payment_audit_payment_created", "payment_id", "created_at"),
    )
