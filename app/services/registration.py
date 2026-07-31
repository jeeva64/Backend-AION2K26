import re

from app.exceptions.api_error import APIError
from app.models.event_registration import EventRegistrationDoc
from app.repositories.event_registration_repository import EventRegistrationRepository
from app.utils.constants import DEGREES, EVENT_SLOT_MAP, FOOD_PREFERENCES, MAX_STUDENTS_PER_LEADER
from app.utils.validators import clean_participant_mobile

_PARTICIPANT_MOBILE = re.compile(r"^[6-9]\d{9}$")


async def register_team(
    event_regs: EventRegistrationRepository,
    *,
    leader_id: str,
    event: str,
    participants: list,
    college: str,
    department: str,
) -> dict:
    slot = EVENT_SLOT_MAP.get(event)
    if slot is None:
        raise APIError(400, "Invalid event selected")

    event_already_taken = await event_regs.find_leader_event(leader_id, event)
    if event_already_taken:
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

        if participant.degree not in DEGREES:
            raise APIError(400, f"Invalid degree for {participant.name}. Must be ug or pg.")

        if not is_existing:
            if not participant.foodPreference:
                raise APIError(400, f"Food preference is required for new participant {participant.name}.")
            if participant.foodPreference not in FOOD_PREFERENCES:
                raise APIError(
                    400,
                    f"Invalid food preference for {participant.name}. Must be vegetarian or non-vegetarian.",
                )

    current_student_count = await event_regs.count_by_leader(leader_id)
    new_student_count = sum(1 for r in reg_numbers if r not in existing_reg_set)
    if current_student_count + new_student_count > MAX_STUDENTS_PER_LEADER:
        raise APIError(
            409,
            f"This would exceed the 15-student limit. Current: {current_student_count}, new in this team: {new_student_count}.",
        )

    for doc in existing_docs:
        if doc.get("event1") == "Bid Mayhem" or doc.get("event2") == "Bid Mayhem":
            raise APIError(
                409,
                f"{doc['name']} ({doc['registerNumber']}) is in Bid Mayhem and cannot register for other events.",
            )
        if slot == "BOTH" and doc.get("event1"):
            raise APIError(
                409,
                f"{doc['name']} ({doc['registerNumber']}) already has events. Bid Mayhem cannot be combined.",
            )
        if doc.get("event2") is not None:
            raise APIError(
                409,
                f"{doc['name']} ({doc['registerNumber']}) is already in 2 events: {doc['event1']} & {doc['event2']}.",
            )
        if doc.get("slot1") == slot:
            raise APIError(
                409,
                f"{doc['name']} ({doc['registerNumber']}) already has {doc['event1']} in the same time slot.",
            )

    created_ids: list = []
    updated_snapshot: list[dict] = []

    try:
        for participant in participants:
            reg_upper = participant.registerNumber.upper()
            clean_mobile = clean_participant_mobile(participant.mobile)
            existing = next((d for d in existing_docs if d["registerNumber"] == reg_upper), None)

            if existing:
                updated_snapshot.append(
                    {"_id": existing["_id"], "prev_event2": existing.get("event2"), "prev_slot2": existing.get("slot2")}
                )
                await event_regs.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"event2": event, "slot2": slot}},
                )
            else:
                new_doc = EventRegistrationDoc(
                    leaderId=leader_id,
                    name=participant.name,
                    registerNumber=reg_upper,
                    mobile=clean_mobile,
                    college=college,
                    department=department,
                    degree=participant.degree,
                    foodPreference=participant.foodPreference,
                    event1=event,
                    slot1=slot,
                )
                result = await event_regs.insert_one(new_doc.model_dump())
                created_ids.append(result.inserted_id)
    except Exception as exc:
        if created_ids:
            await event_regs.delete_many({"_id": {"$in": created_ids}})
        for snapshot in updated_snapshot:
            await event_regs.update_one(
                {"_id": snapshot["_id"]},
                {"$set": {"event2": snapshot["prev_event2"], "slot2": snapshot["prev_slot2"]}},
            )
        raise APIError(500, "Team registration failed and was rolled back. Please try again.") from exc

    return {"created": len(created_ids), "updated": len(updated_snapshot)}
