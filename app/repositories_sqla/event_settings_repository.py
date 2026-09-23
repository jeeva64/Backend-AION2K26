from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_sqla.event_settings import EventSettings


class EventSettingsRepositorySqla:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_deadline(self) -> datetime | None:
        result = await self._session.execute(
            select(EventSettings).where(EventSettings.id == 1)
        )
        obj = result.scalar_one_or_none()
        return obj.registration_deadline if obj else None

    async def set_deadline(self, deadline: datetime | None) -> None:
        await self._session.execute(
            update(EventSettings)
            .where(EventSettings.id == 1)
            .values(registration_deadline=deadline)
        )
        await self._session.flush()
