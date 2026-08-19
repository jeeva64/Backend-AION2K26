from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_sqla.admin import Admin


class AdminRepositorySqla:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._model = Admin

    async def find_by_admin_id(self, admin_id: str) -> dict | None:
        stmt = select(Admin).where(Admin.admin_id == admin_id)
        result = await self._session.execute(stmt)
        obj = result.scalars().first()
        if obj is None:
            return None
        return {
            "id": obj.id,
            "adminId": obj.admin_id,
            "name": obj.name,
            "role": obj.role,
            "password": obj.password_hash,
        }

    async def insert(self, admin_doc: dict) -> None:
        obj = Admin(
            admin_id=admin_doc["adminId"],
            name=admin_doc["name"],
            role=admin_doc["role"],
            password_hash=admin_doc["password"],
        )
        self._session.add(obj)
        await self._session.flush()

    async def update_password(self, admin_id: str, new_password_hash: str) -> bool:
        stmt = (
            update(Admin)
            .where(Admin.admin_id == admin_id)
            .values(password_hash=new_password_hash)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0
