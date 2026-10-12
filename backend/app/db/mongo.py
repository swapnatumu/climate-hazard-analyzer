from pymongo import ASCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.config import Settings


def create_client(settings: Settings) -> AsyncMongoClient:
    # Short server-selection timeout so a misconfigured URI fails fast instead of hanging.
    return AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000, tz_aware=True)


async def ensure_indexes(db: AsyncDatabase) -> None:
    await db.weather_daily.create_index(
        [("cell.lat", ASCENDING), ("cell.lon", ASCENDING), ("year", ASCENDING)], unique=True
    )
    await db.hazard_results.create_index([("computed_at", ASCENDING)])
