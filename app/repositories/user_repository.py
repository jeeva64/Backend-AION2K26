from app.db.mongo import USERS
from app.repositories.base import CollectionRepository


class UserRepository(CollectionRepository):
    collection_name = USERS

    async def find_by_email(self, email: str) -> dict | None:
        return await self.find_one({"email": email})

    async def find_by_mobile(self, mobilenumber: str) -> dict | None:
        return await self.find_one({"mobilenumber": mobilenumber})

    async def find_by_userid(self, userid: str) -> dict | None:
        return await self.find_one({"userid": userid})

    async def find_leader_slot_conflict(self, college: str, department: str, shift: str) -> dict | None:
        return await self.find_one(
            {"college": college, "department": department, "shift": shift}
        )

    async def insert(self, user_doc: dict) -> None:
        await self.insert_one(user_doc)
