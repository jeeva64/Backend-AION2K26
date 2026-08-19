from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_sqla.college import College


class CollegeRepositorySqla:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._model = College

    async def find_all(self) -> list[dict]:
        stmt = (
            select(
                College.college_id,
                College.name,
                College.state,
                College.district,
                College.registered_status,
            )
            .order_by(College.name.asc())
        )
        result = await self._session.execute(stmt)
        return [
            {
                "collegeId": row.college_id,
                "name": row.name,
                "state": row.state,
                "district": row.district,
                "registeredStatus": row.registered_status,
            }
            for row in result.all()
        ]

    async def mark_registered(self, name: str) -> None:
        stmt = (
            update(College)
            .where(College.name == name, College.registered_status.is_(False))
            .values(registered_status=True)
        )
        await self._session.execute(stmt)

    async def insert_many(self, colleges: list[dict]) -> int:
        """Insert all colleges, skipping duplicate ``collegeId`` values.

        Each row is inserted inside a nested SAVEPOINT so that a uniqueness
        violation (or any per-row error) only aborts that row, not the outer
        transaction. Returns the number of rows actually inserted.
        """
        inserted = 0
        for c in colleges:
            obj = College(
                college_id=c["collegeId"],
                name=c["name"],
                state=c.get("state") or "",
                district=c.get("district") or "",
                registered_status=bool(c.get("registeredStatus", False)),
            )
            async with self._session.begin_nested():
                self._session.add(obj)
                await self._session.flush()
                inserted += 1
        return inserted

    async def update_college(
        self, college_id: str, data: dict
    ) -> bool:
        values = {}
        if "collegeId" in data:
            values[College.college_id] = data["collegeId"]
        if "name" in data:
            values[College.name] = data["name"]
        if "state" in data:
            values[College.state] = data["state"]
        if "district" in data:
            values[College.district] = data["district"]
        if not values:
            return False
        stmt = (
            update(College)
            .where(College.college_id == college_id)
            .values(**values)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0
