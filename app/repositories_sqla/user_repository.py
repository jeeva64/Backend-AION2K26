from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_sqla.user import User


class UserRepositorySqla:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._model = User

    def _to_dict(self, obj: User | None) -> dict | None:
        if obj is None:
            return None
        return {
            "userid": obj.user_id,
            "name": obj.name,
            "email": obj.email,
            "mobilenumber": obj.mobile_number,
            "department": obj.department,
            "college": obj.college_name_text,
            "college_id": obj.college_id,
            "shift": obj.shift,
            "password": obj.password_hash,
        }

    async def find_by_email(self, email: str) -> dict | None:
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return self._to_dict(result.scalars().first())

    async def find_by_mobile(self, mobilenumber: str) -> dict | None:
        stmt = select(User).where(User.mobile_number == mobilenumber)
        result = await self._session.execute(stmt)
        return self._to_dict(result.scalars().first())

    async def find_by_userid(self, userid: str) -> dict | None:
        stmt = select(User).where(User.user_id == userid)
        result = await self._session.execute(stmt)
        return self._to_dict(result.scalars().first())

    async def find_leader_slot_conflict(
        self, college: str, department: str, shift: str
    ) -> dict | None:
        stmt = select(User).where(
            User.college_name_text == college,
            User.department == department,
            User.shift == shift,
        )
        result = await self._session.execute(stmt)
        return self._to_dict(result.scalars().first())

    async def insert(self, user_doc: dict) -> None:
        obj = User(
            user_id=user_doc["userid"],
            name=user_doc["name"],
            email=user_doc["email"],
            mobile_number=user_doc["mobilenumber"],
            department=user_doc["department"],
            college_name_text=user_doc["college"],
            shift=user_doc["shift"],
            password_hash=user_doc["password"],
        )
        self._session.add(obj)
        await self._session.flush()

    async def find_distinct_college_departments(self) -> list[dict]:
        stmt = (
            select(User.college_name_text, User.department)
            .distinct()
            .order_by(User.college_name_text, User.department)
        )
        result = await self._session.execute(stmt)
        college_map: dict[str, list[str]] = {}
        for college, dept in result.all():
            college_map.setdefault(college, []).append(dept)
        return [
            {"college": c, "departments": d}
            for c, d in sorted(college_map.items())
        ]
