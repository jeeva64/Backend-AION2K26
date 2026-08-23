"""Payment workflow business logic.

All state transitions are guarded single-session operations -- the FastAPI
get_db dependency commits on success and rolls back on any exception, so
payment + registration status changes are atomic.

Status machines:
  payments.payment_status:
    PENDING -> VERIFICATION_PENDING -> SUCCESS
    VERIFICATION_PENDING -> REJECTED -> (resubmit) -> VERIFICATION_PENDING
    REJECTED -> (reopen, Super Admin) -> VERIFICATION_PENDING
  event_registrations.status mirrors the payment for the leader's rows.
"""
import io
import re
import uuid

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.exceptions.api_error import APIError
from app.repositories_sqla import (
    EventRegistrationRepositorySqla,
    PaymentRepositorySqla,
)
from app.services.fees import calculate_registration_fee, normalize_utr
from app.storage.proof_storage import ProofStorageError, get_proof_storage
from app.utils.constants import ALLOWED_PROOF_FORMATS, PAYMENT_LOCKED_STATUSES

_UTR_RE = re.compile(r"^[A-Za-z0-9]{8,22}$")


async def ensure_payment_for_registration(
    session: AsyncSession,
    payments: PaymentRepositorySqla,
    leader_id: str,
    expected_paises: int,
    unique_count: int,
) -> dict:
    """Create-or-refresh the leader's single payment row after /registerteam.

    Race-safe via SAVEPOINT: two concurrent first-registrations for the same
    leader cannot both INSERT (UNIQUE leader_id); the loser updates instead.
    """
    existing = await payments.find_by_leader(leader_id)
    if existing is None:
        try:
            async with session.begin_nested():
                await payments.insert_pending(leader_id, expected_paises)
        except IntegrityError:
            pass
        existing = await payments.find_by_leader(leader_id)
        if existing is not None and existing["paymentStatus"] == "PENDING" and existing["submittedAmountPaises"] is None:
            await payments.insert_audit(
                existing["_id"],
                admin_id=None,
                action="CREATED",
                old_status=None,
                new_status="PENDING",
                details={
                    "expectedAmountPaises": expected_paises,
                    "uniqueStudents": unique_count,
                },
            )
            return existing
    await payments.update_expected_amount(leader_id, expected_paises)
    return await payments.find_by_leader(leader_id)


def assert_team_edits_allowed(payment: dict | None) -> None:
    """409 when team edits are locked (proof submitted or verified)."""
    if payment and payment["paymentStatus"] in PAYMENT_LOCKED_STATUSES:
        raise APIError(
            409,
            "Team changes are locked while your payment is under review or "
            "confirmed. Contact an organizer for modifications.",
        )


def _validate_proof_file(data: bytes, filename: str) -> tuple[str, str]:
    """Sniff actual image content via Pillow. Returns (ext, mime). Raises 400."""
    max_bytes = settings.PROOF_MAX_MB * 1024 * 1024
    if len(data) == 0:
        raise APIError(400, "Payment screenshot is empty")
    if len(data) > max_bytes:
        raise APIError(
            400, f"Screenshot must be {settings.PROOF_MAX_MB} MB or smaller"
        )

    fmt = None
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
    except UnidentifiedImageError:
        pass
    except Exception:
        pass

    ext = ALLOWED_PROOF_FORMATS.get(fmt or "")
    if ext is None:
        raise APIError(
            400,
            "Unsupported file type. Upload a JPG, PNG or WebP screenshot "
            f"({settings.PROOF_MAX_MB} MB max).",
        )

    mime = {
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }[ext]
    return ext, mime


async def submit_payment_proof(
    session: AsyncSession,
    payments: PaymentRepositorySqla,
    event_regs: EventRegistrationRepositorySqla,
    *,
    leader_id: str,
    utr_raw: str | None,
    amount_paises: int | None,
    screenshot: UploadFile | None,
) -> dict:
    """Validate + store proof, transition payment/registrations atomically."""
    payment = await payments.find_by_leader(leader_id)
    if payment is None:
        raise APIError(404, "No registration found. Register your team first.")

    status = payment["paymentStatus"]
    normalized_utr = normalize_utr(utr_raw)

    if status == "VERIFICATION_PENDING" and normalized_utr == payment["utr"]:
        # Idempotent retry of the same submission (double click / network retry).
        return payment
    if status == "SUCCESS":
        raise APIError(409, "Payment is already verified.")
    if status not in ("PENDING", "REJECTED"):
        raise APIError(409, "A different payment proof is already under review.")

    if not utr_raw or not utr_raw.strip():
        raise APIError(400, "UTR / transaction reference is required")
    if not _UTR_RE.match(normalized_utr):
        raise APIError(400, "UTR must be 8-22 letters or digits with no spaces")

    if amount_paises is None or amount_paises <= 0:
        raise APIError(400, "Submitted amount is required")
    # Amount mismatch is NOT rejected here — it is stored as-is and flagged
    # for manual review. Admins see Expected vs Submitted vs Difference.
    # A screenshot/UTR alone can never mark a payment successful.

    if screenshot is None or screenshot.filename is None:
        raise APIError(400, "Payment screenshot is required")
    data = await screenshot.read()
    original_name = screenshot.filename
    try:
        ext, mime = _validate_proof_file(data, original_name)
    except APIError:
        await screenshot.close()
        raise

    storage = get_proof_storage()
    key = f"payment-proofs/{leader_id}/{payment['_id']}/{uuid.uuid4().hex}{ext}"

    try:
        storage.save(key, data, mime)
    except ProofStorageError as exc:
        raise APIError(500, f"Failed to store payment proof: {exc}")

    try:
        try:
            async with session.begin_nested():
                rowcount = await payments.submit_proof_update(
                    payment["_id"],
                    from_statuses=("PENDING", "REJECTED"),
                    utr=normalized_utr,
                    submitted_amount_paises=amount_paises,
                    proof_object_key=key,
                    proof_original_filename=original_name,
                    proof_mime_type=mime,
                    proof_file_size=len(data),
                )
        except IntegrityError:
            storage.delete(key)
            raise APIError(
                409, "This UTR / transaction reference has already been used."
            )
        if rowcount == 0:
            raise APIError(409, "A different payment proof is already under review.")

        await event_regs.update_status_by_leader(
            leader_id,
            "VERIFICATION_PENDING",
            from_statuses=("PAYMENT_PENDING",),
        )
        await payments.insert_audit(
            payment["_id"],
            admin_id=None,
            action="PROOF_SUBMITTED",
            old_status=status,
            new_status="VERIFICATION_PENDING",
            details={
                "utr": normalized_utr,
                "submittedAmountPaises": amount_paises,
                "expectedAmountPaises": payment["expectedAmountPaises"],
            },
        )
    except APIError:
        storage.delete(key)
        raise
    except Exception:
        storage.delete(key)
        raise

    return await payments.find_by_leader(leader_id)


async def verify_payment(
    session: AsyncSession,
    payments: PaymentRepositorySqla,
    event_regs: EventRegistrationRepositorySqla,
    *,
    payment_id: int,
    admin_id: str,
) -> dict:
    payment = await payments.find_by_id(payment_id)
    if payment is None:
        raise APIError(404, "Payment not found")
    if payment["paymentStatus"] != "VERIFICATION_PENDING":
        raise APIError(
            409,
            f"Only payments in VERIFICATION_PENDING can be verified "
            f"(current: {payment['paymentStatus']}).",
        )

    rowcount = await payments.mark_verified(payment_id, admin_id)
    if rowcount == 0:
        raise APIError(409, "Payment status changed concurrently. Retry.")

    updated_regs = await event_regs.update_status_by_leader(
        payment["leaderId"], "CONFIRMED", from_statuses=("VERIFICATION_PENDING",)
    )
    await payments.insert_audit(
        payment_id,
        admin_id=admin_id,
        action="VERIFIED",
        old_status="VERIFICATION_PENDING",
        new_status="SUCCESS",
    )
    result = await payments.find_by_id(payment_id)
    if result is not None:
        result["confirmedRegistrations"] = updated_regs
    return result


async def reject_payment(
    session: AsyncSession,
    payments: PaymentRepositorySqla,
    event_regs: EventRegistrationRepositorySqla,
    *,
    payment_id: int,
    admin_id: str,
    reason: str,
) -> dict:
    payment = await payments.find_by_id(payment_id)
    if payment is None:
        raise APIError(404, "Payment not found")
    if payment["paymentStatus"] != "VERIFICATION_PENDING":
        raise APIError(
            409,
            f"Only payments in VERIFICATION_PENDING can be rejected "
            f"(current: {payment['paymentStatus']}).",
        )

    rowcount = await payments.mark_rejected(payment_id, reason.strip())
    if rowcount == 0:
        raise APIError(409, "Payment status changed concurrently. Retry.")

    reverted = await event_regs.update_status_by_leader(
        payment["leaderId"], "PAYMENT_PENDING", from_statuses=("VERIFICATION_PENDING",)
    )
    await payments.insert_audit(
        payment_id,
        admin_id=admin_id,
        action="REJECTED",
        old_status="VERIFICATION_PENDING",
        new_status="REJECTED",
        reason=reason.strip(),
    )
    result = await payments.find_by_id(payment_id)
    if result is not None:
        result["revertedRegistrations"] = reverted
    return result


async def reopen_payment(
    session: AsyncSession,
    payments: PaymentRepositorySqla,
    event_regs: EventRegistrationRepositorySqla,
    *,
    payment_id: int,
    admin_id: str,
) -> dict:
    payment = await payments.find_by_id(payment_id)
    if payment is None:
        raise APIError(404, "Payment not found")
    if payment["paymentStatus"] != "REJECTED":
        raise APIError(
            409,
            f"Only REJECTED payments can be reopened (current: {payment['paymentStatus']}).",
        )

    rowcount = await payments.reopen(payment_id)
    if rowcount == 0:
        raise APIError(409, "Payment status changed concurrently. Retry.")

    promoted = await event_regs.update_status_by_leader(
        payment["leaderId"], "VERIFICATION_PENDING", from_statuses=("PAYMENT_PENDING",)
    )
    await payments.insert_audit(
        payment_id,
        admin_id=admin_id,
        action="REOPENED",
        old_status="REJECTED",
        new_status="VERIFICATION_PENDING",
    )
    result = await payments.find_by_id(payment_id)
    if result is not None:
        result["promotedRegistrations"] = promoted
    return result


def build_payment_summary(payment: dict | None, upi_uri: str | None) -> dict:
    """Leader-facing summary shape used by /payments/mine."""
    if payment is None:
        return {"payment": None, "upiUri": upi_uri}
    allowed = {
        "paymentId",
        "leaderId",
        "expectedAmountPaises",
        "submittedAmountPaises",
        "currency",
        "utr",
        "paymentStatus",
        "submittedAt",
        "verifiedAt",
        "rejectionReason",
    }
    return {
        "payment": {k: v for k, v in payment.items() if k in allowed},
        "upiUri": upi_uri,
    }
