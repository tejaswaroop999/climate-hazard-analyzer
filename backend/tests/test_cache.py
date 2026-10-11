import asyncio
import os
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.repositories.cache import MongoCache, cache_key
from app.schemas import AnalysisRequest
from app.services.analysis import AnalysisService, select_records
from app.services.climate import dates_between


class MemoryCache:
    """Test double only: the application always requires real MongoDB."""

    def __init__(self):
        self.docs = {}

    async def get(self, collection, key):
        return deepcopy(self.docs.get((collection, key)))

    async def put(self, collection, key, payload):
        now = datetime.now(UTC)
        doc = {
            "payload": deepcopy(payload),
            "created_at": now,
            "expires_at": now + timedelta(days=30),
        }
        self.docs[collection, key] = doc
        return deepcopy(doc)


def test_persisted_results_and_overlapping_raw_cache():
    async def run():
        weather = AsyncMock()

        async def daily(lat, lon, start, end):
            return {
                "records": [(d.isoformat(), 20.0) for d in dates_between(start, end)],
                "grid_latitude": lat,
                "grid_longitude": lon,
                "timezone": "Asia/Kolkata",
            }

        weather.daily.side_effect = daily
        cache = MemoryCache()
        service = AnalysisService(cache, weather)
        request = AnalysisRequest(
            latitude=17.0, longitude=78.0, start_year=2000, end_year=2020
        )
        first = await service.execute(request)
        count = weather.daily.call_count
        second = await service.execute(request)
        assert not first["cache"]["hit"] and second["cache"]["hit"]
        assert weather.daily.call_count == count
        overlap = request.model_copy(update={"start_year": 2005})
        await service.execute(overlap)
        assert weather.daily.call_count == count
        assert first["summary"] == second["summary"]
        assert first["data_quality"]["out_of_range_dates"] == 0

    asyncio.run(run())


def test_key_order_and_algorithm_version():
    assert cache_key({"a": 1, "b": 2}) == cache_key({"b": 2, "a": 1})
    assert cache_key({"algorithm": 1}) != cache_key({"algorithm": 2})


@pytest.mark.skipif(
    not os.getenv("TEST_MONGO_URI"),
    reason="Set TEST_MONGO_URI for real MongoDB integration",
)
def test_real_mongo_indexes_expiry_and_roundtrip():
    async def run():
        cache = MongoCache(os.environ["TEST_MONGO_URI"], "climate_test", 1)
        key = "integration-" + str(datetime.now().timestamp())
        try:
            await cache.initialize()
            await cache.put("analyses", key, {"value": 42})
            assert (await cache.get("analyses", key))["payload"] == {"value": 42}
            indexes = await cache.db.analyses.index_information()
            assert any(i.get("unique") for i in indexes.values())
            assert any(i.get("expireAfterSeconds") == 0 for i in indexes.values())
            await cache.db.analyses.update_one(
                {"key": key},
                {"$set": {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}},
            )
            assert await cache.get("analyses", key) is None
        finally:
            await cache.db.analyses.delete_one({"key": key})
            await cache.close()

    asyncio.run(run())


def test_concurrent_overlapping_requests_share_downloads():
    async def run():
        weather = AsyncMock()

        async def daily(lat, lon, start, end):
            await asyncio.sleep(0)
            return {
                "records": [(d.isoformat(), 20.0) for d in dates_between(start, end)],
                "grid_latitude": lat,
                "grid_longitude": lon,
                "timezone": "Asia/Kolkata",
            }

        weather.daily.side_effect = daily
        service = AnalysisService(MemoryCache(), weather)
        first = AnalysisRequest(
            latitude=17.0, longitude=78.0, start_year=2000, end_year=2020
        )
        second = first.model_copy(update={"start_year": 2005})
        await asyncio.gather(service.execute(first), service.execute(second))
        assert weather.daily.call_count == 4

    asyncio.run(run())


def test_malformed_dates_survive_period_selection_for_quality_reporting():
    rows = [("not-a-date", 20), ("2000-01-01", 20), ("1990-01-01", 20)]
    assert select_records(rows, date(2000, 1, 1), date(2000, 12, 31)) == rows[:2]
