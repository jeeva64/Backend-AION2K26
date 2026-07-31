from app.db.mongo import COLLEGES
from app.repositories.base import CollectionRepository


class CollegeRepository(CollectionRepository):
    collection_name = COLLEGES

    async def find_all(self) -> list[dict]:
        return await self.find(
            {},
            {"_id": 0, "collegeId": 1, "name": 1, "district": 1, "registeredStatus": 1},
            sort=[("name", 1)],
        )

    async def mark_registered(self, name: str) -> None:
        await self.update_one(
            {"name": name, "registeredStatus": False},
            {"$set": {"registeredStatus": True}},
        )
