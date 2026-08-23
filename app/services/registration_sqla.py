import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.api_error import APIError
from app.models_sqla.event import Event, EventSlot
from app.models_sqla.event_registration import EventRegistration
from app.utils.constants import FOOD_PREFERENCES, MAX_STUDENTS_PER_LEADER
from app.utils.validators import clean_participant_mobile

_PARTICIPANT_MOBILE = re.compile(r"^[6-9]\d{9}$")


async def _resolve_event(session: AsyncSession, event_name: str) -> tuple[Event, EventSlot]:
    stmt = (
        select(Event, EventSlot)
        .join(EventSlot, Event.slot_id == EventSlot.id)
        .where(Event.name == event_name)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        raise APIError(400, "Invalid event selected")
    return row[0], row[1]


async def register_team(
    session: AsyncSession,
    event_regs,  # EventRegistrationRepositorySqla, shares the same session
    *,
    leader_id: str,
    event: str,
    participants: list,
    college: str,
    department: str,
) -> dict:
    """Register/update a team in one transaction (Postgres).

    The Mongo version used manual compensation on failure; with a real
    transactional backend we let the surrounding AsyncSession rollback on
    any exception. Returns ``{"created": n, "updated": n}``.
    """
    srv_event, srv_slot = await _resolve_event(session, event)
    slot_label = srv_slot.slot_label

    # One team per event per leader.
    if await event_regs.find_leader_event(leader_id, event):
        raise APIError(
            409,
            f"Your team is already registered for {event}. Only one team per event is allowed.",
        )

    reg_numbers = [(p.registerNumber or "").upper() for p in participants]

    seen: set[str] = set()
    for reg_number in reg_numbers:
        if reg_number in seen:
            raise APIError(400, f"Duplicate register numbers in team: {reg_number}")
        seen.add(reg_number)

    existing_docs = await event_regs.find_team_by_register_numbers(leader_id, reg_numbers)
    existing_reg_set = {doc["registerNumber"] for doc in existing_docs}

    for participant in participants:
        is_existing = (participant.registerNumber or "").upper() in existing_reg_set

        if not participant.name or not participant.registerNumber or not participant.mobile or not participant.degree:
            raise APIError(
                400,
                "Incomplete data for a participant. name, registerNumber, mobile and degree are all required.",
            )

        if not _PARTICIPANT_MOBILE.match(clean_participant_mobile(participant.mobile)):
            raise APIError(
                400,
                f"Invalid mobile number for {participant.name}. Must be 10 digits starting with 6-9.",
            )

        if participant.foodPreference and participant.foodPreference not in FOOD_PREFERENCES:
            raise APIError(
                400,
                f"Invalid food preference for {participant.name}. Must be vegetarian or non-vegetarian.",
            )

        if not is_existing:
            if not participant.foodPreference:
                raise APIError(400, f"Food preference is required for new participant {participant.name}.")

    current_student_count = await event_regs.count_by_leader(leader_id)
    new_student_count = sum(1 for r in reg_numbers if r not in existing_reg_set)
    if current_student_count + new_student_count > MAX_STUDENTS_PER_LEADER:
        raise APIError(
            409,
            f"This would exceed the 15-student limit. Current: {current_student_count}, new in this team: {new_student_count}.",
        )

    for doc in existing_docs:
        if doc.get("event2") == "Bid Mayhem" or doc.get("event1") == "Bid Mayhem":
            raise APIError(
                409,
                f"{doc['name']} ({doc['registerNumber']}) is in Bid Mayhem and cannot register for other events.",
            )
        if slot_label == "BOTH" and doc.get("event1"):
            raise APIError(
                409,
                f"{doc['name']} ({doc['registerNumber']}) already has events. Bid Mayhem cannot be combined.",
            )
        if doc.get("event2") is not None:
            raise APIError(
                409,
                f"{doc['name']} ({doc['registerNumber']}) is already in 2 events: {doc['event1']} & {doc['event2']}.",
            )
        if doc.get("slot1") == slot_label:
            raise APIError(
                409,
                f"{doc['name']} ({doc['registerNumber']}) already has {doc['event1']} in the same time slot.",
            )

    created = 0
    updated = 0

    for participant in participants:
        reg_upper = participant.registerNumber.upper()
        clean_mobile = clean_participant_mobile(participant.mobile)
        existing = next((d for d in existing_docs if d["registerNumber"] == reg_upper), None)

        if existing:
            stmt = (
                select(EventRegistration)
                .where(EventRegistration.id == existing["_id"])
            )
            obj = (await session.execute(stmt)).scalars().first()
            obj.event2_id = srv_event.id
            obj.slot2_id = srv_slot.id
            await session.flush()
            updated += 1
        else:
            new_obj = EventRegistration(
                leader_id=leader_id,
                name=participant.name,
                register_number=reg_upper,
                mobile=clean_mobile,
                college_name_text=college,
                department=department,
                degree=participant.degree,
                food_preference=participant.foodPreference,
                event1_id=srv_event.id,
                slot1_id=srv_slot.id,
                status="PAYMENT_PENDING",
            )
            session.add(new_obj)
            await session.flush()
            created += 1

    return {"created": created, "updated": updated}
