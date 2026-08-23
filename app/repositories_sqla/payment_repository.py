from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_sqla.admin import Admin
from app.models_sqla.payment import Payment, PaymentAudit
from app.models_sqla.user import User


class PaymentRepositorySqla:
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_dict(self, obj: Payment | None) -> dict | None:
        if obj is None:
            return None
        return {
            "_id": obj.id,
            "paymentId": obj.id,
            "leaderId": obj.leader_id,
            "expectedAmountPaises": obj.expected_amount_paises,
            "submittedAmountPaises": obj.submitted_amount_paises,
            "currency": obj.currency,
            "utr": obj.utr,
            "paymentStatus": obj.payment_status,
            "proofObjectKey": obj.proof_object_key,
            "proofOriginalFilename": obj.proof_original_filename,
            "proofMimeType": obj.proof_mime_type,
            "proofFileSize": obj.proof_file_size,
            "submittedAt": obj.submitted_at,
            "verifiedAt": obj.verified_at,
            "verifiedBy": obj.verified_by,
            "rejectionReason": obj.rejection_reason,
        }

    @staticmethod
    def _to_audit_dict(obj: PaymentAudit) -> dict:
        return {
            "_id": obj.id,
            "auditId": obj.id,
            "paymentId": obj.payment_id,
            "adminId": obj.admin_id,
            "action": obj.action,
            "oldStatus": obj.old_status,
            "newStatus": obj.new_status,
            "reason": obj.reason,
            "details": obj.details,
            "createdAt": obj.created_at,
        }

    async def find_by_leader(self, leader_id: str) -> dict | None:
        stmt = select(Payment).where(Payment.leader_id == leader_id)
        result = await self._session.execute(stmt)
        return self._to_dict(result.scalars().first())

    async def find_by_id(self, payment_id: int) -> dict | None:
        stmt = select(Payment).where(Payment.id == payment_id)
        result = await self._session.execute(stmt)
        return self._to_dict(result.scalars().first())

    async def insert_pending(
        self, leader_id: str, expected_amount_paises: int
    ) -> None:
        self._session.add(
            Payment(
                leader_id=leader_id,
                expected_amount_paises=expected_amount_paises,
                payment_status="PENDING",
            )
        )
        await self._session.flush()

    async def update_expected_amount(
        self, leader_id: str, expected_amount_paises: int
    ) -> None:
        stmt = (
            update(Payment)
            .where(Payment.leader_id == leader_id)
            .values(expected_amount_paises=expected_amount_paises)
        )
        await self._session.execute(stmt)

    async def submit_proof_update(
        self,
        payment_id: int,
        *,
        from_statuses: tuple[str, ...],
        utr: str,
        submitted_amount_paises: int,
        proof_object_key: str,
        proof_original_filename: str,
        proof_mime_type: str,
        proof_file_size: int,
    ) -> int:
        """Guarded transition to VERIFICATION_PENDING. Returns rowcount."""
        stmt = (
            update(Payment)
            .where(
                Payment.id == payment_id,
                Payment.payment_status.in_(from_statuses),
            )
            .values(
                utr=utr,
                submitted_amount_paises=submitted_amount_paises,
                proof_object_key=proof_object_key,
                proof_original_filename=proof_original_filename,
                proof_mime_type=proof_mime_type,
                proof_file_size=proof_file_size,
                submitted_at=func.now(),
                payment_status="VERIFICATION_PENDING",
                rejection_reason=None,
                verified_by=None,
                verified_at=None,
            )
            .execution_options(synchronize_session=False)
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def mark_verified(self, payment_id: int, admin_id: str) -> int:
        """Guarded VERIFICATION_PENDING → SUCCESS. Returns rowcount."""
        stmt = (
            update(Payment)
            .where(
                Payment.id == payment_id,
                Payment.payment_status == "VERIFICATION_PENDING",
            )
            .values(
                payment_status="SUCCESS",
                verified_by=admin_id,
                verified_at=func.now(),
            )
            .execution_options(synchronize_session=False)
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def mark_rejected(self, payment_id: int, reason: str) -> int:
        """Guarded VERIFICATION_PENDING → REJECTED. Returns rowcount."""
        stmt = (
            update(Payment)
            .where(
                Payment.id == payment_id,
                Payment.payment_status == "VERIFICATION_PENDING",
            )
            .values(payment_status="REJECTED", rejection_reason=reason)
            .execution_options(synchronize_session=False)
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def reopen(self, payment_id: int) -> int:
        """Guarded REJECTED → VERIFICATION_PENDING (Super Admin action)."""
        stmt = (
            update(Payment)
            .where(Payment.id == payment_id, Payment.payment_status == "REJECTED")
            .values(payment_status="VERIFICATION_PENDING", rejection_reason=None)
            .execution_options(synchronize_session=False)
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def list_payments(self, status: str | None = None) -> list[dict]:
        stmt = select(Payment, User, Admin).join(
            User, Payment.leader_id == User.user_id, isouter=True
        ).join(Admin, Payment.verified_by == Admin.admin_id, isouter=True)
        if status:
            stmt = stmt.where(Payment.payment_status == status)
        stmt = stmt.order_by(Payment.submitted_at.desc().nulls_last(), Payment.id.desc())
        result = await self._session.execute(stmt)
        out: list[dict] = []
        for payment, user, admin in result.all():
            d = self._to_dict(payment) or {}
            d["leaderName"] = user.name if user else None
            d["leaderCollege"] = user.college_name_text if user else None
            d["leaderDepartment"] = user.department if user else None
            d["verifierName"] = admin.name if admin else None
            out.append(d)
        return out

    async def insert_audit(
        self,
        payment_id: int,
        *,
        admin_id: str | None,
        action: str,
        old_status: str | None,
        new_status: str | None,
        reason: str | None = None,
        details: dict | None = None,
    ) -> None:
        self._session.add(
            PaymentAudit(
                payment_id=payment_id,
                admin_id=admin_id,
                action=action,
                old_status=old_status,
                new_status=new_status,
                reason=reason,
                details=details,
            )
        )
        await self._session.flush()

    async def list_audit(self, payment_id: int) -> list[dict]:
        stmt = (
            select(PaymentAudit)
            .where(PaymentAudit.payment_id == payment_id)
            .order_by(PaymentAudit.created_at.asc(), PaymentAudit.id.asc())
        )
        result = await self._session.execute(stmt)
        return [self._to_audit_dict(o) for o in result.scalars().all()]
