from typing import Any

from app.db.mongo import EVENT_REGISTRATIONS
from app.repositories.base import CollectionRepository


class EventRegistrationRepository(CollectionRepository):
    collection_name = EVENT_REGISTRATIONS

    async def find_by_leader(self, leader_id: str) -> list[dict]:
        return await self.find({"leaderId": leader_id})

    async def find_leader_event(self, leader_id: str, event: str) -> dict | None:
        return await self.find_one(
            {"leaderId": leader_id, "$or": [{"event1": event}, {"event2": event}]}
        )

    async def find_team_by_register_numbers(self, leader_id: str, register_numbers: list[str]) -> list[dict]:
        return await self.find(
            {"leaderId": leader_id, "registerNumber": {"$in": register_numbers}}
        )

    async def count_by_leader(self, leader_id: str) -> int:
        return await self.count_documents({"leaderId": leader_id})

    async def count_leader_event(self, leader_id: str, event: str) -> int:
        return await self.count_documents(
            {"leaderId": leader_id, "$or": [{"event1": event}, {"event2": event}]}
        )

    async def find_team(self, college: str, department: str) -> list[dict]:
        return await self.find({"college": college, "department": department})

    async def find_by_leader_and_event(self, leader_id: str, event: str) -> list[dict]:
        return await self.find(
            {"leaderId": leader_id, "$or": [{"event1": event}, {"event2": event}]}
        )

    async def promote_event2_to_event1(self, doc_id: Any, event2: str, slot2: Any) -> None:
        await self.update_one(
            {"_id": doc_id},
            {"$set": {"event1": event2, "slot1": slot2, "event2": None, "slot2": None}},
        )

    async def clear_event2(self, doc_id: Any) -> None:
        await self.update_one(
            {"_id": doc_id},
            {"$set": {"event2": None, "slot2": None}},
        )

    async def delete_many_by_leader(self, leader_id: str) -> int:
        result = await self.delete_many({"leaderId": leader_id})
        return result.deleted_count
