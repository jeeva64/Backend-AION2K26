import secrets
import time

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import get_current_super_admin, get_current_user
from app.auth.security import create_access_token, hash_password, verify_password
from app.config.settings import settings
from app.dependencies.db import AsyncSessionDep
from app.dependencies.repositories import (
    get_college_repo,
    get_event_regs_repo,
    get_payment_repo,
    get_user_repo,
)
from app.exceptions.api_error import APIError
from app.middleware.rate_limit import limiter
from app.repositories_sqla import (
    CollegeRepositorySqla,
    EventRegistrationRepositorySqla,
    PaymentRepositorySqla,
    UserRepositorySqla,
)
from app.schemas.auth import (
    AddCollegeResponse,
    GetCandidatesRequest,
    GetCandidatesResponse,
    GetCollegeResponse,
    LeaderLoginRequest,
    LeaderLoginResponse,
    LeaderRegisterRequest,
    LeaderRegisterResponse,
    RegisterTeamRequest,
    RegisterTeamResponse,
    StatsResponse,
)
from app.schemas.common import success
from app.schemas.payment import MyPaymentsResponse, SubmitProofResponse
from app.services.fees import build_upi_uri, calculate_registration_fee
from app.services.payment_sqla import (
    assert_team_edits_allowed,
    build_payment_summary,
    ensure_payment_for_registration,
    submit_payment_proof,
)
from app.services.registration_sqla import register_team
from app.utils.constants import CURRENCY
from app.utils.serializers import sanitize
from app.utils.validators import clean_mobile_number

router = APIRouter()


async def _generate_leader_id(users: UserRepositorySqla) -> str:
    while True:
        candidate = f"LD{int(time.time() * 1000)}{secrets.randbelow(1000)}"
        if not await users.find_by_userid(candidate):
            return candidate


@router.post("/regleader", status_code=201, response_model=LeaderRegisterResponse)
async def register_leader(
    payload: LeaderRegisterRequest,
    session: AsyncSessionDep,
    users: UserRepositorySqla = Depends(get_user_repo),
    colleges: CollegeRepositorySqla = Depends(get_college_repo),
):
    normalized_email = payload.email.strip().lower()
    if await users.find_by_email(normalized_email):
        raise APIError(400, "Email already registered")

    clean_mobile = clean_mobile_number(payload.mobilenumber)
    if await users.find_by_mobile(clean_mobile):
        raise APIError(400, "Mobile number already registered")

    if await users.find_leader_slot_conflict(
        payload.college.strip(), payload.department.strip(), payload.shift.strip()
    ):
        raise APIError(400, "Leader already exists for this College, Department and Shift")

    leader_id = await _generate_leader_id(users)

    try:
        await users.insert(
            {
                "userid": leader_id,
                "name": payload.name.strip(),
                "email": normalized_email,
                "mobilenumber": clean_mobile,
                "department": payload.department.strip(),
                "college": payload.college.strip(),
                "shift": payload.shift.strip(),
                "password": hash_password(payload.password),
            }
        )
        await session.flush()
    except IntegrityError:
        raise APIError(400, "Registration failed. Email or mobile number is already registered.")

    await colleges.mark_registered(payload.college.strip())

    return success("Leader registered successfully", userid=leader_id)


@router.post("/loginleader", response_model=LeaderLoginResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login_leader(
    request: Request,
    payload: LeaderLoginRequest,
    users: UserRepositorySqla = Depends(get_user_repo),
):
    normalized_email = payload.email.strip().lower()
    user = await users.find_by_email(normalized_email)
    if not user or not verify_password(payload.password, user["password"]):
        raise APIError(401, "Invalid Email or Password")

    token = create_access_token(
        {"userid": user["userid"], "email": user["email"], "name": user["name"], "role": "user"}
    )
    return success("Login successful", userid=user["userid"], name=user["name"], token=token)


@router.post("/registerteam", response_model=RegisterTeamResponse)
async def register_team_route(
    payload: RegisterTeamRequest,
    session: AsyncSessionDep,
    current_user: dict = Depends(get_current_user),
    users: UserRepositorySqla = Depends(get_user_repo),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
    payments: PaymentRepositorySqla = Depends(get_payment_repo),
):
    if payload.leaderId != current_user["userid"]:
        raise APIError(403, "Access denied. Leader ID mismatch.")

    leader = await users.find_by_userid(payload.leaderId)
    if not leader:
        raise APIError(404, "Leader not found")

    college = leader.get("college")
    department = leader.get("department")
    if not college or not department:
        raise APIError(400, "Leader profile incomplete. Missing college or department.")

    assert_team_edits_allowed(await payments.find_by_leader(payload.leaderId))

    result = await register_team(
        session,
        event_regs,
        leader_id=payload.leaderId,
        event=payload.event,
        participants=payload.participants,
        college=college,
        department=department,
    )

    unique_count = await event_regs.count_distinct_students(payload.leaderId)
    amount_due = calculate_registration_fee(unique_count)
    await ensure_payment_for_registration(
        session, payments, payload.leaderId, amount_due, unique_count
    )
    payment = await payments.find_by_leader(payload.leaderId)

    return success(
        f"Team of {len(payload.participants)} registered for {payload.event}.",
        created=result["created"],
        updated=result["updated"],
        uniqueStudents=unique_count,
        amountDuePaises=amount_due,
        currency=CURRENCY,
        upiUri=build_upi_uri(payload.leaderId, amount_due),
        paymentStatus=payment["paymentStatus"] if payment else "PENDING",
    )


@router.get("/payments/mine", response_model=MyPaymentsResponse)
async def my_payments(
    current_user: dict = Depends(get_current_user),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
    payments: PaymentRepositorySqla = Depends(get_payment_repo),
):
    leader_id = current_user["userid"]
    unique_count = await event_regs.count_distinct_students(leader_id)
    amount_due = calculate_registration_fee(unique_count)
    payment = await payments.find_by_leader(leader_id)
    summary = build_payment_summary(payment, build_upi_uri(leader_id, amount_due))
    return success(
        "Payment details fetched successfully",
        uniqueStudents=unique_count,
        amountDuePaises=payment["expectedAmountPaises"] if payment else amount_due,
        upiUri=summary["upiUri"],
        data=sanitize(summary["payment"]),
    )


@router.post("/payments/proof", response_model=SubmitProofResponse)
async def submit_proof_route(
    session: AsyncSessionDep,
    screenshot: UploadFile | None = File(None),
    utr: str | None = Form(None),
    amountPaises: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
    payments: PaymentRepositorySqla = Depends(get_payment_repo),
):
    payment = await submit_payment_proof(
        session,
        payments,
        event_regs,
        leader_id=current_user["userid"],
        utr_raw=utr,
        amount_paises=amountPaises,
        screenshot=screenshot,
    )
    return success("Payment proof submitted for verification",
                   paymentId=payment["paymentId"],
                   paymentStatus=payment["paymentStatus"])


@router.post("/getcandidates", response_model=GetCandidatesResponse)
async def get_candidates(
    payload: GetCandidatesRequest,
    current_user: dict = Depends(get_current_user),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
):
    if not payload.user_id:
        raise APIError(400, "User ID required")
    if payload.user_id != current_user["userid"]:
        raise APIError(403, "Access denied. User ID mismatch.")

    students = await event_regs.find_by_leader(payload.user_id)

    registered_events: set[str] = set()
    for student in students:
        if student.get("event1"):
            registered_events.add(student["event1"])
        if student.get("event2"):
            registered_events.add(student["event2"])

    return success(
        "Candidates fetched successfully",
        totalStudents=len(students),
        registeredEvents=list(registered_events),
        data=sanitize(students),
    )


@router.get("/stats/{leader_id}", response_model=StatsResponse)
async def get_stats(
    leader_id: str,
    current_user: dict = Depends(get_current_user),
    event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
):
    if leader_id != current_user["userid"]:
        raise APIError(403, "Access denied. Leader ID mismatch.")

    students = await event_regs.find_by_leader(leader_id)

    registered_events: set[str] = set()
    for student in students:
        if student.get("event1"):
            registered_events.add(student["event1"])
        if student.get("event2"):
            registered_events.add(student["event2"])

    return success(
        "Stats fetched successfully",
        stats={
            "totalStudents": len(students),
            "studentsRemaining": 15 - len(students),
            "eventsRegistered": len(registered_events),
            "registeredEvents": list(registered_events),
        },
    )


@router.post("/addcollege", status_code=201, response_model=AddCollegeResponse)
async def add_college(
    colleges: list[dict],
    current_admin: dict = Depends(get_current_super_admin),
    colleges_repo: CollegeRepositorySqla = Depends(get_college_repo),
):
    if not colleges:
        raise APIError(400, "Send array of colleges")

    for college in colleges:
        if not college.get("collegeId") or not college.get("name"):
            raise APIError(400, "Each college must have collegeId and name")

    inserted = await colleges_repo.insert_many(colleges)
    if inserted == 0:
        raise APIError(400, "No colleges were added. Duplicate collegeId values detected.")

    return success("Colleges added successfully", count=inserted)


@router.get("/getcollege", response_model=GetCollegeResponse)
async def get_college(colleges_repo: CollegeRepositorySqla = Depends(get_college_repo)):
    colleges = await colleges_repo.find_all()
    return success("Colleges fetched successfully", data=sanitize(colleges))
