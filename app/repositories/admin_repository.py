from app.db.mongo import ADMINS
from app.repositories.base import CollectionRepository


class AdminRepository(CollectionRepository):
    collection_name = ADMINS

    async def find_by_admin_id(self, admin_id: str) -> dict | None:
        return await self.find_one({"adminId": admin_id})

    async def insert(self, admin_doc: dict) -> None:
        await self.insert_one(admin_doc)
