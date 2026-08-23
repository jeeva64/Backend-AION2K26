"""Postgres equivalents of the Mongo aggregation pipelines in services.stats.")

Returns the same nested dict shapes that the routers/contracts expect:
  - dashboard_stats -> stats dict with totalMembers, totalTeams, vegCount,
    nonVegCount, ugCount, pgCount, eventCounts, collegeStats, deptCounts
  - view_event_regs -> list of {leaderId, college, department, members: [...]}
Each member dict keeps the camelCase keys the frontend uses (event1/slot1/...).
"""
from sqlalchemy import case, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_sqla.event import Event, EventSlot
from app.models_sqla.event_registration import EventRegistration
from app.utils.constants import EVENTS


async def dashboard_stats(session: AsyncSession) -> dict:
    total_members = int(
        (await session.execute(select(func.count()).select_from(EventRegistration))).scalar_one()
    )

    food_rows = (
        await session.execute(
            select(EventRegistration.food_preference, func.count())
            .group_by(EventRegistration.food_preference)
        )
    ).all()
    veg_count = next((c for f, c in food_rows if f == "vegetarian"), 0)
    non_veg_count = next((c for f, c in food_rows if f == "non-vegetarian"), 0)

    degree_rows = (
        await session.execute(
            select(EventRegistration.degree, func.count())
            .group_by(EventRegistration.degree)
        )
    ).all()
    ug_count = next((c for d, c in degree_rows if d == "ug"), 0)
    pg_count = next((c for d, c in degree_rows if d == "pg"), 0)

    total_teams = int(
        (
            await session.execute(
                select(func.count(func.distinct(
                    func.concat(
                        EventRegistration.leader_id, "|",
                        EventRegistration.college_name_text, "|",
                        EventRegistration.department,
                    )
                )))
            )
        ).scalar_one()
    )

    # Single set-based query for every per-event count instead of one
    # id-lookup + one COUNT per event (~16 round trips). Both event columns
    # are UNION ALL'd and joined to events; a row can never have
    # event1 = event2 (CHECK constraint), so nothing is double counted.
    membership = select(EventRegistration.event1_id.label("event_id")).union_all(
        select(EventRegistration.event2_id).where(
            EventRegistration.event2_id.isnot(None)
        )
    ).subquery()
    count_rows = (
        await session.execute(
            select(Event.name, func.count())
            .join(membership, Event.id == membership.c.event_id)
            .group_by(Event.name)
        )
    ).all()
    counts_by_name = {name: int(c) for name, c in count_rows}
    event_counts: dict[str, int] = {
        name: counts_by_name.get(name, 0) for name in EVENTS
    }

    college_stats_rows = (
        await session.execute(
            select(
                EventRegistration.college_name_text.label("college"),
                EventRegistration.department.label("department"),
                func.count().label("members"),
                func.sum(
                    case(
                        (EventRegistration.food_preference == "vegetarian", 1),
                        else_=0,
                    )
                ).label("veg"),
                func.sum(
                    case(
                        (EventRegistration.food_preference == "non-vegetarian", 1),
                        else_=0,
                    )
                ).label("nonVeg"),
            )
            .group_by(
                EventRegistration.college_name_text,
                EventRegistration.department,
            )
        )
    ).all()
    college_stats = [
        {
            "college": row.college,
            "department": row.department,
            "members": row.members,
            "veg": int(row.veg or 0),
            "nonVeg": int(row.nonVeg or 0),
        }
        for row in college_stats_rows
    ]

    dept_rows = (
        await session.execute(
            select(EventRegistration.department, func.count())
            .group_by(EventRegistration.department)
        )
    ).all()
    dept_counts = {(d or "unknown"): int(c) for d, c in dept_rows}

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


async def view_event_regs(session: AsyncSession, event_name: str) -> list[dict]:
    """Group registrations for one event by leader (matches the Mongo pipeline)."""
    ev = (
        await session.execute(select(Event).where(Event.name == event_name))
    ).scalars().first()
    if ev is None:
        return []

    stmt = (
        select(EventRegistration)
        .where(
            or_(
                EventRegistration.event1_id == ev.id,
                EventRegistration.event2_id == ev.id,
            )
        )
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return []

    events_map = {e.id: e.name for e in (await session.execute(select(Event))).scalars().all()}
    slots_map = {
        s.id: s.slot_label for s in (await session.execute(select(EventSlot))).scalars().all()
    }

    members_by_leader: dict[str, dict] = {}
    for r in rows:
        bucket = members_by_leader.setdefault(
            r.leader_id,
            {"leaderId": r.leader_id, "college": r.college_name_text, "department": r.department, "members": []},
        )
        bucket["members"].append(
            {
                "name": r.name,
                "registerNumber": r.register_number,
                "mobile": r.mobile,
                "degree": r.degree,
                "foodPreference": r.food_preference,
                "event1": events_map.get(r.event1_id),
                "slot1": slots_map.get(r.slot1_id),
                "event2": events_map.get(r.event2_id) if r.event2_id else None,
                "slot2": slots_map.get(r.slot2_id) if r.slot2_id else None,
            }
        )
    # suppress unused import lint warning for literal_column
    _ = literal_column
    return list(members_by_leader.values())
