"""Data access for the two collections.

Queries are built only from validated scalars (floats, ints, hex keys), never from raw
request dicts, so a `$`-operator can't be injected.
"""

from typing import Protocol

from pymongo import ReplaceOne
from pymongo.asynchronous.database import AsyncDatabase

from app.services.grid import Cell


class WeatherRepo(Protocol):
    async def get_years(self, cell: Cell, years: list[int]) -> dict[int, dict]: ...
    async def upsert_years(self, docs: list[dict]) -> None: ...


class ResultRepo(Protocol):
    async def get(self, key: str) -> dict | None: ...
    async def put(self, doc: dict) -> None: ...


class MongoWeatherRepo:
    """`weather_daily`: one document per grid cell per year, values as parallel arrays."""

    def __init__(self, db: AsyncDatabase):
        self.col = db.weather_daily

    async def get_years(self, cell: Cell, years: list[int]) -> dict[int, dict]:
        cursor = self.col.find(
            {"cell.lat": float(cell.lat), "cell.lon": float(cell.lon),
             "year": {"$in": [int(y) for y in years]}},
        )
        return {doc["year"]: doc async for doc in cursor}

    async def upsert_years(self, docs: list[dict]) -> None:
        if docs:
            await self.col.bulk_write(
                [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs], ordered=False
            )


class MongoResultRepo:
    """`hazard_results`: cached analysis output keyed by a hash of all its inputs."""

    def __init__(self, db: AsyncDatabase):
        self.col = db.hazard_results

    async def get(self, key: str) -> dict | None:
        return await self.col.find_one({"_id": str(key)})

    async def put(self, doc: dict) -> None:
        await self.col.replace_one({"_id": doc["_id"]}, doc, upsert=True)
