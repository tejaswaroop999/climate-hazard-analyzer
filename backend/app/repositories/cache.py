import hashlib
import json
from datetime import UTC, datetime, timedelta

from pymongo import ASCENDING, AsyncMongoClient


class MongoCache:
    def __init__(self, uri, database, ttl_days):
        self.client = AsyncMongoClient(
            uri, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000, tz_aware=True
        )
        self.db = self.client[database]
        self.ttl = timedelta(days=ttl_days)

    async def initialize(self):
        await self.ping()
        for name in ("analyses", "weather"):
            await self.db[name].create_index([("key", ASCENDING)], unique=True)
            await self.db[name].create_index("expires_at", expireAfterSeconds=0)

    async def ping(self):
        await self.client.admin.command("ping")

    async def get(self, collection, key):
        # Mongo TTL cleanup is asynchronous; exclude expired documents ourselves.
        return await self.db[collection].find_one(
            {"key": key, "expires_at": {"$gt": datetime.now(UTC)}}, {"_id": 0}
        )

    async def put(self, collection, key, payload):
        now = datetime.now(UTC)
        document = {
            "key": key,
            "created_at": now,
            "expires_at": now + self.ttl,
            "payload": payload,
        }
        await self.db[collection].update_one(
            {"key": key}, {"$set": document}, upsert=True
        )
        return document

    async def close(self):
        await self.client.close()


def cache_key(parts):
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
