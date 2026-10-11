import asyncio
from datetime import date, datetime, timezone
from fastapi.concurrency import run_in_threadpool
from app.repositories.cache import cache_key
from app.services.climate import analyze, ALGORITHM_VERSION
from app.services.weather import MODEL, WeatherError


def select_records(records, start, end):
    selected = []
    for day, value in records:
        try:
            parsed = date.fromisoformat(day)
        except (TypeError, ValueError):
            # Preserve malformed dates for transparent quality accounting.
            selected.append((day, value))
            continue
        if start <= parsed <= end:
            selected.append((day, value))
    return selected


class AnalysisService:
    def __init__(self, cache, weather):
        self.cache, self.weather = cache, weather
        # Fixed stripes bound lock memory and prevent duplicate downloads in one process.
        self.locks = [asyncio.Lock() for _ in range(64)]
        self.analysis_slots = asyncio.Semaphore(4)
        self.weather_locks = [asyncio.Lock() for _ in range(64)]

    async def execute(self, request):
        async with self.analysis_slots:
            return await self._execute(request)

    async def _execute(self, request):
        parts = {
            **request.model_dump(),
            "algorithm": ALGORITHM_VERSION,
            "model": MODEL,
            "baseline": "1991-2020",
            "timezone": "auto",
            "unit": "celsius",
        }
        key = cache_key(parts)
        async with self.locks[int(key[:8], 16) % len(self.locks)]:
            cached = await self.cache.get("analyses", key)
            if cached:
                return self._response(cached, True)
            # Decade blocks allow overlapping analysis periods to share weather downloads.
            years = set(range(request.start_year, request.end_year + 1)) | set(
                range(1991, 2021)
            )
            blocks = sorted({year // 10 * 10 for year in years})
            all_records, provenance = [], []
            for first in blocks:
                last = min(first + 9, datetime.now(timezone.utc).year - 1)
                weather_key = cache_key(
                    {
                        "lat": request.latitude,
                        "lon": request.longitude,
                        "start": first,
                        "end": last,
                        "model": MODEL,
                        "unit": "celsius",
                        "timezone": "auto",
                        "schema": 1,
                    }
                )
                async with self.weather_locks[
                    int(weather_key[:8], 16) % len(self.weather_locks)
                ]:
                    raw = await self.cache.get("weather", weather_key)
                    if raw is None:
                        payload = await self.weather.daily(
                            request.latitude,
                            request.longitude,
                            date(first, 1, 1),
                            date(last, 12, 31),
                        )
                        raw = await self.cache.put("weather", weather_key, payload)
                payload = raw["payload"]
                all_records.extend(payload["records"])
                provenance.append({k: v for k, v in payload.items() if k != "records"})
            start, end = date(request.start_year, 1, 1), date(request.end_year, 12, 31)
            selected = select_records(all_records, start, end)
            baseline = select_records(all_records, date(1991, 1, 1), date(2020, 12, 31))
            metadata_fields = (
                "timezone",
                "grid_latitude",
                "grid_longitude",
                "unit",
                "model",
            )
            if any(
                any(
                    p.get(field) != provenance[0].get(field)
                    for field in metadata_fields
                )
                for p in provenance
            ):
                raise WeatherError(
                    "Weather provider returned inconsistent grid or timezone metadata"
                )
            result = await run_in_threadpool(analyze, selected, baseline, start, end)
            result["region"] = {
                "latitude": request.latitude,
                "longitude": request.longitude,
                "spatial_method": "nearest ERA5 grid cell; point analysis",
            }
            result["source"] = {
                "provider": "Open-Meteo",
                "model": MODEL,
                "temperature_unit": "Celsius",
                "timezone": provenance[0]["timezone"],
                "grid_latitude": provenance[0]["grid_latitude"],
                "grid_longitude": provenance[0]["grid_longitude"],
                "attribution": "Weather data by Open-Meteo.com; ERA5 by Copernicus/ECMWF",
            }
            stored = await self.cache.put("analyses", key, result)
            # Return the persisted document, satisfying the database-first read contract.
            stored = await self.cache.get("analyses", key) or stored
            return self._response(stored, False)

    @staticmethod
    def _response(document, hit):
        return {
            **document["payload"],
            "cache": {
                "hit": hit,
                "created_at": document["created_at"].isoformat(),
                "expires_at": document["expires_at"].isoformat(),
            },
        }
