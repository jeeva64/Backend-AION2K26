from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_sqla.event import Event, EventSlot
from app.models_sqla.event_registration import EventRegistration


class EventRegistrationRepositorySqla:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._model = EventRegistration
        self._event_model = Event
        self._slot_model = EventSlot

    def _to_dict(self, obj: EventRegistration | None) -> dict | None:
        if obj is None:
            return None
        return {
            "_id": obj.id,
            "leaderId": obj.leader_id,
            "name": obj.name,
            "registerNumber": obj.register_number,
            "mobile": obj.mobile,
            "college": obj.college_name_text,
            "department": obj.department,
            "degree": obj.degree,
            "foodPreference": obj.food_preference,
            "event1_id": obj.event1_id,
            "slot1_id": obj.slot1_id,
            "event2_id": obj.event2_id,
            "slot2_id": obj.slot2_id,
            "event1": None,  # populated by callers via _resolve_event_names
            "slot1": None,
            "event2": None,
            "slot2": None,
        }

    async def _resolve_events_map(self) -> dict[int, str]:
        stmt = select(Event.id, Event.name)
        result = await self._session.execute(stmt)
        return {row.id: row.name for row in result.all()}

    async def _resolve_slots_map(self) -> dict[int, str]:
        stmt = select(EventSlot.id, EventSlot.slot_label)
        result = await self._session.execute(stmt)
        return {row.id: row.slot_label for row in result.all()}

    async def _hydrate(self, obj: EventRegistration) -> dict:
        events = await self._resolve_events_map()
        slots = await self._resolve_slots_map()
        d = self._to_dict(obj)
        d["event1"] = events.get(obj.event1_id)
        d["slot1"] = slots.get(obj.slot1_id)
        d["event2"] = events.get(obj.event2_id) if obj.event2_id else None
        d["slot2"] = slots.get(obj.slot2_id) if obj.slot2_id else None
        return d

    async def find_by_leader(self, leader_id: str) -> list[dict]:
        stmt = select(EventRegistration).where(EventRegistration.leader_id == leader_id)
        result = await self._session.execute(stmt)
        objs = result.scalars().all()
        return [await self._hydrate(o) for o in objs]

    async def find_leader_event(self, leader_id: str, event_name: str) -> dict | None:
        stmt_events = select(Event.id).where(Event.name == event_name)
        result_ev = await self._session.execute(stmt_events)
        event_id = result_ev.scalars().first()
        if event_id is None:
            return None
        stmt = select(EventRegistration).where(
            EventRegistration.leader_id == leader_id,
            (EventRegistration.event1_id == event_id)
            | (EventRegistration.event2_id == event_id),
        )
        result = await self._session.execute(stmt)
        obj = result.scalars().first()
        return await self._hydrate(obj) if obj else None

    async def find_team_by_register_numbers(
        self, leader_id: str, register_numbers: list[str]
    ) -> list[dict]:
        stmt = select(EventRegistration).where(
            EventRegistration.leader_id == leader_id,
            EventRegistration.register_number.in_(register_numbers),
        )
        result = await self._session.execute(stmt)
        return [await self._hydrate(o) for o in result.scalars().all()]

    async def count_by_leader(self, leader_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(EventRegistration)
            .where(EventRegistration.leader_id == leader_id)
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def find_team(self, college: str, department: str) -> list[dict]:
        stmt = select(EventRegistration).where(
            EventRegistration.college_name_text == college,
            EventRegistration.department == department,
        )
        result = await self._session.execute(stmt)
        return [await self._hydrate(o) for o in result.scalars().all()]

    async def find_by_leader_and_event(
        self, leader_id: str, event_name: str
    ) -> list[dict]:
        stmt_events = select(Event.id).where(Event.name == event_name)
        event_id = (await self._session.execute(stmt_events)).scalars().first()
        if event_id is None:
            return []
        stmt = select(EventRegistration).where(
            EventRegistration.leader_id == leader_id,
            (EventRegistration.event1_id == event_id)
            | (EventRegistration.event2_id == event_id),
        )
        result = await self._session.execute(stmt)
        return [await self._hydrate(o) for o in result.scalars().all()]

    async def promote_event2_to_event1(
        self, doc_id: int, event2_id: int, slot2_id: int | None
    ) -> None:
        stmt = (
            update(EventRegistration)
            .where(EventRegistration.id == doc_id)
            .values(
                event1_id=event2_id,
                slot1_id=slot2_id,
                event2_id=None,
                slot2_id=None,
            )
        )
        await self._session.execute(stmt)

    async def clear_event2(self, doc_id: int) -> None:
        stmt = (
            update(EventRegistration)
            .where(EventRegistration.id == doc_id)
            .values(event2_id=None, slot2_id=None)
        )
        await self._session.execute(stmt)

    async def delete_many_by_leader(self, leader_id: str) -> int:
        stmt = (
            delete(EventRegistration)
            .where(EventRegistration.leader_id == leader_id)
            .execution_options(synchronize_session=False)
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def delete_one(self, doc_id: int) -> None:
        stmt = (
            delete(EventRegistration)
            .where(EventRegistration.id == doc_id)
            .execution_options(synchronize_session=False)
        )
        await self._session.execute(stmt)

    async def count_leader_event(self, leader_id: str, event_name: str) -> int:
        stmt_events = select(Event.id).where(Event.name == event_name)
        event_id = (await self._session.execute(stmt_events)).scalars().first()
        if event_id is None:
            return 0
        stmt = (
            select(func.count())
            .select_from(EventRegistration)
            .where(
                EventRegistration.leader_id == leader_id,
                (EventRegistration.event1_id == event_id)
                | (EventRegistration.event2_id == event_id),
            )
        )
        return int((await self._session.execute(stmt)).scalar_one())
