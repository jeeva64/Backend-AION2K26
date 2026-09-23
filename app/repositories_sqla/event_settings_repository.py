from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_sqla.event_settings import EventSettings
from app.repositories_sqla.base import mapping_one


class EventSettingsRepositorySqla:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_deadline(self) -> datetime | None:
        row = await mapping_one(
            self._session, select(EventSettings).where(EventSettings.id == 1)
        )
        return row["registration_deadline"] if row else None

    async def set_deadline(self, deadline: datetime | None) -> None:
        exists = await self.get_deadline()
        if exists is None:
            self._session.add(EventSettings(id=1, registration_deadline=deadline))
            await self._session.flush()
        else:
            await self._session.execute(
                update(EventSettings)
                .where(EventSettings.id == 1)
                .values(registration_deadline=deadline)
            )
            await self._session.flush()
