import asyncio
from datetime import date

import httpx

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
MODEL = "era5"


class WeatherError(Exception):
    """A safe message can be returned to clients without leaking upstream internals."""


class WeatherProvider:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.slots = asyncio.Semaphore(3)

    async def _get(self, url, params):
        async with self.slots:
            for attempt in range(3):
                try:
                    response = await self.client.get(url, params=params)
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < 2:
                            await asyncio.sleep(0.5 * 2**attempt)
                            continue
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict) or data.get("error"):
                        raise WeatherError(
                            "Weather provider returned an invalid response"
                        )
                    return data
                except httpx.RequestError:
                    if attempt < 2:
                        await asyncio.sleep(0.5 * 2**attempt)
                        continue
                    raise WeatherError(
                        "Weather provider is unavailable or timed out"
                    ) from None
                except (httpx.HTTPStatusError, ValueError):
                    raise WeatherError(
                        "Weather provider returned an invalid response"
                    ) from None
        raise WeatherError("Weather provider is unavailable")

    async def daily(self, latitude: float, longitude: float, start: date, end: date):
        data = await self._get(
            ARCHIVE_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": "temperature_2m_max",
                "temperature_unit": "celsius",
                "timezone": "auto",
                "models": MODEL,
            },
        )
        try:
            if data["daily_units"]["temperature_2m_max"] != "\u00b0C":
                raise WeatherError(
                    "Weather provider returned unsupported temperature units"
                )
            days = data["daily"]["time"]
            values = data["daily"]["temperature_2m_max"]
            if (
                not isinstance(days, list)
                or not isinstance(values, list)
                or len(days) != len(values)
            ):
                raise WeatherError(
                    "Weather provider returned inconsistent daily arrays"
                )
            if not isinstance(data.get("latitude"), (int, float)) or not isinstance(
                data.get("longitude"), (int, float)
            ):
                raise WeatherError(
                    "Weather provider did not identify its grid coordinates"
                )
            if not isinstance(data.get("timezone"), str):
                raise WeatherError("Weather provider did not identify its timezone")
            return {
                "records": list(zip(days, values, strict=True)),
                "grid_latitude": data.get("latitude"),
                "grid_longitude": data.get("longitude"),
                "timezone": data["timezone"],
                "unit": "Celsius",
                "model": MODEL,
            }
        except (KeyError, TypeError):
            raise WeatherError(
                "Weather provider returned malformed daily data"
            ) from None

    async def search(self, query):
        data = await self._get(
            GEOCODING_URL,
            {"name": query, "count": 8, "language": "en", "format": "json"},
        )
        results = data.get("results", [])
        if not isinstance(results, list):
            raise WeatherError("Location provider returned malformed results")
        output = []
        try:
            for row in results:
                lat, lon = row["latitude"], row["longitude"]
                if (
                    not isinstance(lat, (int, float))
                    or not isinstance(lon, (int, float))
                    or not -90 <= lat <= 90
                    or not -180 <= lon <= 180
                ):
                    raise WeatherError("Location provider returned invalid coordinates")
                if not isinstance(row["name"], str):
                    raise WeatherError("Location provider returned an invalid name")
                output.append(
                    {
                        "name": row["name"],
                        "latitude": lat,
                        "longitude": lon,
                        "admin1": row.get("admin1", ""),
                        "country": row.get("country", ""),
                    }
                )
        except (KeyError, TypeError):
            raise WeatherError("Location provider returned malformed results") from None
        return output
