from app.repositories.event_registration_repository import EventRegistrationRepository
from app.utils.constants import EVENTS


async def dashboard_stats(event_regs: EventRegistrationRepository) -> dict:
    registrations = event_regs.collection

    total_members = await registrations.count_documents({})

    food_rows = await registrations.aggregate(
        [{"$group": {"_id": "$foodPreference", "count": {"$sum": 1}}}]
    ).to_list(None)
    veg_count = next((r["count"] for r in food_rows if r["_id"] == "vegetarian"), 0)
    non_veg_count = next((r["count"] for r in food_rows if r["_id"] == "non-vegetarian"), 0)

    degree_rows = await registrations.aggregate(
        [{"$group": {"_id": "$degree", "count": {"$sum": 1}}}]
    ).to_list(None)
    ug_count = next((r["count"] for r in degree_rows if r["_id"] == "ug"), 0)
    pg_count = next((r["count"] for r in degree_rows if r["_id"] == "pg"), 0)

    team_rows = await registrations.aggregate(
        [
            {"$group": {"_id": {"college": "$college", "department": "$department", "leaderId": "$leaderId"}}},
            {"$count": "total"},
        ]
    ).to_list(None)
    total_teams = team_rows[0]["total"] if team_rows else 0

    event_counts = {}
    for event in EVENTS:
        event_counts[event] = await registrations.count_documents(
            {"$or": [{"event1": event}, {"event2": event}]}
        )

    college_stats = await registrations.aggregate(
        [
            {
                "$group": {
                    "_id": {"college": "$college", "department": "$department"},
                    "members": {"$sum": 1},
                    "veg": {"$sum": {"$cond": [{"$eq": ["$foodPreference", "vegetarian"]}, 1, 0]}},
                    "nonVeg": {"$sum": {"$cond": [{"$eq": ["$foodPreference", "non-vegetarian"]}, 1, 0]}},
                }
            },
            {
                "$project": {
                    "college": "$_id.college",
                    "department": "$_id.department",
                    "members": 1,
                    "veg": 1,
                    "nonVeg": 1,
                    "_id": 0,
                }
            },
        ]
    ).to_list(None)

    dept_rows = await registrations.aggregate(
        [{"$group": {"_id": {"$ifNull": ["$department", "unknown"]}, "count": {"$sum": 1}}}]
    ).to_list(None)
    dept_counts = {row["_id"]: row["count"] for row in dept_rows}

    return {
        "totalMembers": total_members,
        "totalTeams": total_teams,
        "vegCount": veg_count,
        "nonVegCount": non_veg_count,
        "ugCount": ug_count,
        "pgCount": pg_count,
        "eventCounts": event_counts,
        "collegeStats": college_stats,
        "deptCounts": dept_counts,
    }


async def view_event_regs(event_regs: EventRegistrationRepository, event_name: str) -> list[dict]:
    pipeline = [
        {"$match": {"$or": [{"event1": event_name}, {"event2": event_name}]}},
        {
            "$group": {
                "_id": "$leaderId",
                "college": {"$first": "$college"},
                "department": {"$first": "$department"},
                "members": {
                    "$push": {
                        "name": "$name",
                        "registerNumber": "$registerNumber",
                        "mobile": "$mobile",
                        "degree": "$degree",
                        "foodPreference": "$foodPreference",
                        "event1": "$event1",
                        "slot1": "$slot1",
                        "event2": "$event2",
                        "slot2": "$slot2",
                    }
                },
            }
        },
        {
            "$project": {
                "leaderId": "$_id",
                "college": 1,
                "department": 1,
                "members": 1,
                "_id": 0,
            }
        },
    ]
    return await event_regs.aggregate(pipeline)
