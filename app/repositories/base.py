from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo.results import DeleteResult, InsertManyResult, InsertOneResult, UpdateResult


class CollectionRepository:
    """Thin data-access wrapper around a single MongoDB collection."""

    collection_name: str

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self.collection: AsyncIOMotorCollection = db[self.collection_name]

    async def find_one(self, filter: dict, projection: dict | None = None) -> dict | None:
        return await self.collection.find_one(filter, projection)

    async def find(
        self,
        filter: dict | None = None,
        projection: dict | None = None,
        sort: list[tuple] | None = None,
    ) -> list[dict]:
        cursor = self.collection.find(filter or {}, projection)
        if sort is not None:
            cursor = cursor.sort(sort)
        return await cursor.to_list(None)

    async def insert_one(self, document: dict) -> InsertOneResult:
        return await self.collection.insert_one(document)

    async def insert_many(self, documents: list[dict], ordered: bool = False) -> InsertManyResult:
        return await self.collection.insert_many(documents, ordered=ordered)

    async def update_one(self, filter: dict, update: dict, upsert: bool = False) -> UpdateResult:
        return await self.collection.update_one(filter, update, upsert=upsert)

    async def delete_one(self, filter: dict) -> DeleteResult:
        return await self.collection.delete_one(filter)

    async def delete_many(self, filter: dict) -> DeleteResult:
        return await self.collection.delete_many(filter)

    async def count_documents(self, filter: dict) -> int:
        return await self.collection.count_documents(filter)

    async def aggregate(self, pipeline: list[dict]) -> list[dict]:
        return await self.collection.aggregate(pipeline).to_list(None)
