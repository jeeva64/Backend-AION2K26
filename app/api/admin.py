from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import get_current_admin, get_current_super_admin
from app.auth.security import create_access_token, hash_password, verify_password
from app.config.settings import settings
from app.dependencies.db import AsyncSessionDep
from app.dependencies.repositories import (
    get_admin_repo,
    get_college_repo,
    get_event_regs_repo,
    get_payment_repo,
    get_user_repo,
)
from app.exceptions.api_error import APIError
from app.middleware.rate_limit import limiter
from app.repositories_sqla import (
    AdminRepositorySqla,
    CollegeRepositorySqla,
    EventRegistrationRepositorySqla,
    PaymentRepositorySqla,
    UserRepositorySqla,
)
from app.schemas.admin import (
    AdminChangePasswordRequest,
    AdminChangePasswordResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminRegisterRequest,
    AdminRegisterResponse,
    DashboardStatsResponse,
    DeleteTeamByEventResponse,
    DeleteTeamResponse,
    LeaderCollegeDeptsResponse,
    UpdateCollegeRequest,
    UpdateCollegeResponse,
    ViewEventRegsRequest,
    ViewEventRegsResponse,
    ViewTeamRequest,
    ViewTeamResponse,
)
from app.schemas.common import success
from app.schemas.payment import (
    PaymentActionResponse,
    PaymentDetailResponse,
    PaymentListResponse,
    PaymentProofResponse,
    RejectPaymentRequest,
)
from app.services.payment_sqla import (
    reject_payment,
    reopen_payment,
    verify_payment,
)
from app.services.stats_sqla import dashboard_stats, view_event_regs
from app.storage.proof_storage import get_proof_storage
from app.utils.constants import PAYMENT_STATUSES
from app.utils.serializers import sanitize

router = APIRouter()


@router.post("/adminreg", status_code=201, response_model=AdminRegisterResponse)
async def register_admin(
    payload: AdminRegisterRequest,
    session: AsyncSessionDep,
    current_admin: dict = Depends(get_current_super_admin),
    admins: AdminRepositorySqla = Depends(get_admin_repo),
):
    if await admins.find_by_admin_id(payload.adminId):
        raise APIError(400, "Admin already exists")

    try:
        await admins.insert(
            {
                "adminId": payload.adminId,
                "name": payload.name,
                "role": payload.role,
                "password": hash_password(payload.password),
            }
        )
        await session.flush()
    except IntegrityError:
        raise APIError(400, "Admin already exists")

    return success("Admin registered successfully")


@router.post("/adminlogin", response_model=AdminLoginResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login_admin(
    request: Request,
    payload: AdminLoginRequest,
    admins: AdminRepositorySqla = Depends(get_admin_repo),
):
    admin = await admins.find_by_admin_id(payload.adminId)
    if not admin or not verify_password(payload.password, admin["password"]):
        raise APIError(401, "Invalid Admin ID or Password")

    token = create_access_token(
        {"adminId": admin["adminId"], "adminRole": admin["role"], "role": "admin"}
    )
    message = "Super Admin logged in" if admin["role"] == 1 else "Organizer logged in"
    return success(message, role=admin["role"], token=token)


@router.post("/changepassword", response_model=AdminChangePasswordResponse)
async def change_password(
    payload: AdminChangePasswordRequest,
    current_admin: dict = Depends(get_current_admin),
    admins: AdminRepositorySqla = Depends(get_admin_repo),
):
    admin = await admins.find_by_admin_id(current_admin["adminId"])
    if not admin:
        raise APIError(404, "Admin not found")

    if not verify_password(payload.currentPassword, admin["password"]):
        raise APIError(400, "Current password is incorrect")

    if payload.currentPassword == payload.newPassword:
        raise APIError(400, "New password must be different from current password")

    updated = await admins.update_password(admin["adminId"], hash_password(payload.newPassword))
    if not updated:
        raise APIError(500, "Failed to update password")

    return success("Password updated successfully")


@router.post("/viewteam", response_model=ViewTeamResponse)
async def view_team(
    payload: ViewTeamRequest,
    current_admin: dict = Depends(get_current_admin),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
):
    team = await event_regs.find_team(payload.college, payload.department)
    return success("Team fetched successfully", data=sanitize(team))


@router.post("/vieweventregs", response_model=ViewEventRegsResponse)
async def view_event_regs_route(
    payload: ViewEventRegsRequest,
    session: AsyncSessionDep,
    current_admin: dict = Depends(get_current_admin),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
):
    records = await view_event_regs(session, payload.eventName)
    if not records:
        raise APIError(404, "No registrations found")

    return success(
        "Registrations fetched successfully",
        event=payload.eventName,
        totalTeams=len(records),
        data=sanitize(records),
    )


@router.delete("/deleteteam/{leader_id}", response_model=DeleteTeamResponse)
async def delete_team(
    leader_id: str,
    current_admin: dict = Depends(get_current_admin),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
):
    team_count = await event_regs.count_by_leader(leader_id)
    if team_count == 0:
        raise APIError(404, "No team found for this leader")

    deleted = await event_regs.delete_many_by_leader(leader_id)
    return success(
        f"Deleted {deleted} team member(s) for leader {leader_id}",
        deletedCount=deleted,
    )


@router.delete("/deleteteambyevent/{leader_id}/{event}", response_model=DeleteTeamByEventResponse)
async def delete_team_by_event(
    leader_id: str,
    event: str,
    current_admin: dict = Depends(get_current_admin),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
):
    members = await event_regs.find_by_leader_and_event(leader_id, event)
    if not members:
        raise APIError(404, "No registrations found for this event")

    updated = 0
    deleted = 0
    for doc in members:
        if doc.get("event1") == event:
            if doc.get("event2"):
                await event_regs.promote_event2_to_event1(doc["_id"], doc["event2_id"], doc["slot2_id"])
                updated += 1
            else:
                await event_regs.delete_one(doc["_id"])
                deleted += 1
        elif doc.get("event2") == event:
            await event_regs.clear_event2(doc["_id"])
            updated += 1

    return success(
        f"Team removed from {event}. {updated} member(s) updated, {deleted} member(s) deleted.",
        updatedCount=updated,
        deletedCount=deleted,
    )


@router.get("/dashboardstats", response_model=DashboardStatsResponse)
async def dashboard_stats_route(
    session: AsyncSessionDep,
    current_admin: dict = Depends(get_current_admin),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
):
    stats = await dashboard_stats(session)
    return success("Dashboard stats fetched successfully", stats=stats)


@router.put("/college/{college_id}", response_model=UpdateCollegeResponse)
async def update_college(
    college_id: str,
    payload: UpdateCollegeRequest,
    current_admin: dict = Depends(get_current_super_admin),
    colleges: CollegeRepositorySqla = Depends(get_college_repo),
):
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not data:
        raise APIError(400, "No fields to update")

    updated = await colleges.update_college(college_id, data)
    if not updated:
        raise APIError(404, "College not found")

    return success("College updated successfully")


@router.get("/leader-college-depts", response_model=LeaderCollegeDeptsResponse)
async def leader_college_depts(
    current_admin: dict = Depends(get_current_admin),
    users: UserRepositorySqla = Depends(get_user_repo),
):
    data = await users.find_distinct_college_departments()
    return success("College departments fetched successfully", data=data)


@router.get("/payments", response_model=PaymentListResponse)
async def list_payments(
    status: str | None = None,
    current_admin: dict = Depends(get_current_super_admin),
    payments: PaymentRepositorySqla = Depends(get_payment_repo),
):
    if status and status not in PAYMENT_STATUSES:
        raise APIError(400, f"Invalid payment status. Use one of: {', '.join(PAYMENT_STATUSES)}")
    rows = await payments.list_payments(status)
    return success("Payments fetched successfully", count=len(rows), data=sanitize(rows))


@router.get("/payments/{payment_id}", response_model=PaymentDetailResponse)
async def payment_detail(
    payment_id: int,
    current_admin: dict = Depends(get_current_super_admin),
    payments: PaymentRepositorySqla = Depends(get_payment_repo),
):
    payment = await payments.find_by_id(payment_id)
    if payment is None:
        raise APIError(404, "Payment not found")
    audit = await payments.list_audit(payment_id)
    return success("Payment fetched successfully", data=sanitize(payment), audit=sanitize(audit))


@router.get("/payments/{payment_id}/proof", response_model=PaymentProofResponse)
async def payment_proof_url(
    payment_id: int,
    current_admin: dict = Depends(get_current_super_admin),
    payments: PaymentRepositorySqla = Depends(get_payment_repo),
):
    payment = await payments.find_by_id(payment_id)
    if payment is None:
        raise APIError(404, "Payment not found")
    if not payment["proofObjectKey"]:
        raise APIError(404, "No proof uploaded for this payment")

    storage = get_proof_storage()
    if storage.supports_signed_urls:
        url = storage.signed_url(payment["proofObjectKey"], expires_in=300)
        expires = 300
    else:
        # Local/dev backend — stream through the authorized content endpoint.
        url = f"/admin/payments/{payment_id}/proof/content"
        expires = 300
    return success(
        "Proof URL generated",
        url=url,
        expiresIn=expires,
        mimeType=payment["proofMimeType"],
        originalFilename=payment["proofOriginalFilename"],
    )


@router.get("/payments/{payment_id}/proof/content")
async def payment_proof_content(
    payment_id: int,
    current_admin: dict = Depends(get_current_super_admin),
    payments: PaymentRepositorySqla = Depends(get_payment_repo),
):
    """Authorized proof streaming — screenshots are never publicly reachable."""
    payment = await payments.find_by_id(payment_id)
    if payment is None or not payment["proofObjectKey"]:
        raise APIError(404, "No proof uploaded for this payment")

    data = get_proof_storage().get_bytes(payment["proofObjectKey"])
    if data is None:
        raise APIError(404, "Proof object missing from storage")
    return Response(
        content=data,
        media_type=payment["proofMimeType"] or "application/octet-stream",
    )


@router.post("/payments/{payment_id}/verify", response_model=PaymentActionResponse)
async def verify_payment_route(
    payment_id: int,
    session: AsyncSessionDep,
    current_admin: dict = Depends(get_current_super_admin),
    payments: PaymentRepositorySqla = Depends(get_payment_repo),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
):
    payment = await verify_payment(
        session,
        payments,
        event_regs,
        payment_id=payment_id,
        admin_id=current_admin["adminId"],
    )
    return success(
        "Payment verified. Registration confirmed.",
        paymentStatus=payment["paymentStatus"],
    )


@router.post("/payments/{payment_id}/reject", response_model=PaymentActionResponse)
async def reject_payment_route(
    payment_id: int,
    payload: RejectPaymentRequest,
    session: AsyncSessionDep,
    current_admin: dict = Depends(get_current_super_admin),
    payments: PaymentRepositorySqla = Depends(get_payment_repo),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
):
    payment = await reject_payment(
        session,
        payments,
        event_regs,
        payment_id=payment_id,
        admin_id=current_admin["adminId"],
        reason=payload.reason.strip(),
    )
    return success(
        "Payment rejected. Leader may resubmit proof.",
        paymentStatus=payment["paymentStatus"],
    )


@router.post("/payments/{payment_id}/reopen", response_model=PaymentActionResponse)
async def reopen_payment_route(
    payment_id: int,
    session: AsyncSessionDep,
    current_admin: dict = Depends(get_current_super_admin),
    payments: PaymentRepositorySqla = Depends(get_payment_repo),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
):
    payment = await reopen_payment(
        session,
        payments,
        event_regs,
        payment_id=payment_id,
        admin_id=current_admin["adminId"],
    )
    return success(
        "Payment reopened for review.",
        paymentStatus=payment["paymentStatus"],
    )
