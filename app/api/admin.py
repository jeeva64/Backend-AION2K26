from fastapi import APIRouter, Depends, Request
from pymongo.errors import DuplicateKeyError

from app.auth.dependencies import get_current_admin, get_current_super_admin
from app.auth.security import create_access_token, hash_password, verify_password
from app.config.settings import settings
from app.dependencies.repositories import get_admin_repo, get_event_regs_repo
from app.exceptions.api_error import APIError
from app.middleware.rate_limit import limiter
from app.models.admin import AdminDoc
from app.repositories import AdminRepository, EventRegistrationRepository
from app.schemas.admin import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminRegisterRequest,
    AdminRegisterResponse,
    DashboardStatsResponse,
    DeleteTeamByEventResponse,
    DeleteTeamResponse,
    ViewEventRegsRequest,
    ViewEventRegsResponse,
    ViewTeamRequest,
    ViewTeamResponse,
)
from app.schemas.common import success
from app.services.stats import dashboard_stats, view_event_regs
from app.utils.serializers import sanitize

router = APIRouter()


@router.post("/adminreg", status_code=201, response_model=AdminRegisterResponse)
async def register_admin(
    payload: AdminRegisterRequest,
    current_admin: dict = Depends(get_current_super_admin),
    admins: AdminRepository = Depends(get_admin_repo),
):
    if await admins.find_by_admin_id(payload.adminId):
        raise APIError(400, "Admin already exists")

    admin_doc = AdminDoc(
        adminId=payload.adminId,
        name=payload.name,
        role=payload.role,
        password=hash_password(payload.password),
    )
    try:
        await admins.insert(admin_doc.model_dump())
    except DuplicateKeyError:
        raise APIError(400, "Admin already exists")

    return success("Admin registered successfully")


@router.post("/adminlogin", response_model=AdminLoginResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login_admin(
    request: Request,
    payload: AdminLoginRequest,
    admins: AdminRepository = Depends(get_admin_repo),
):
    admin = await admins.find_by_admin_id(payload.adminId)
    if not admin or not verify_password(payload.password, admin["password"]):
        raise APIError(401, "Invalid Admin ID or Password")

    token = create_access_token(
        {"adminId": admin["adminId"], "adminRole": admin["role"], "role": "admin"}
    )
    message = "Super Admin logged in" if admin["role"] == 1 else "Organizer logged in"
    return success(message, role=admin["role"], token=token)


@router.post("/viewteam", response_model=ViewTeamResponse)
async def view_team(
    payload: ViewTeamRequest,
    current_admin: dict = Depends(get_current_admin),
    event_regs: EventRegistrationRepository = Depends(get_event_regs_repo),
):
    team = await event_regs.find_team(payload.college, payload.department)
    return success("Team fetched successfully", data=sanitize(team))


@router.post("/vieweventregs", response_model=ViewEventRegsResponse)
async def view_event_regs_route(
    payload: ViewEventRegsRequest,
    current_admin: dict = Depends(get_current_admin),
    event_regs: EventRegistrationRepository = Depends(get_event_regs_repo),
):
    records = await view_event_regs(event_regs, payload.eventName)
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
    event_regs: EventRegistrationRepository = Depends(get_event_regs_repo),
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
    event_regs: EventRegistrationRepository = Depends(get_event_regs_repo),
):
    members = await event_regs.find_by_leader_and_event(leader_id, event)
    if not members:
        raise APIError(404, "No registrations found for this event")

    updated = 0
    deleted = 0
    for doc in members:
        if doc.get("event1") == event:
            if doc.get("event2"):
                await event_regs.promote_event2_to_event1(doc["_id"], doc["event2"], doc.get("slot2"))
                updated += 1
            else:
                await event_regs.delete_one({"_id": doc["_id"]})
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
    current_admin: dict = Depends(get_current_admin),
    event_regs: EventRegistrationRepository = Depends(get_event_regs_repo),
):
    stats = await dashboard_stats(event_regs)
    return success("Dashboard stats fetched successfully", stats=stats)
