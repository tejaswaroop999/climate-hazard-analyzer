import asyncio
from datetime import date
import httpx
import pytest
from app.services.weather import WeatherProvider, WeatherError


def fetch(body, status=200):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body))
        ) as client:
            return await WeatherProvider(client).daily(
                17, 78, date(2000, 1, 1), date(2000, 1, 2)
            )

    return asyncio.run(run())


def test_explicit_units_and_malformed_arrays():
    good = {
        "daily_units": {"temperature_2m_max": "\u00b0C"},
        "daily": {"time": ["2000-01-01"], "temperature_2m_max": [None]},
        "timezone": "Asia/Kolkata",
        "latitude": 17.0,
        "longitude": 78.0,
    }
    assert fetch(good)["records"] == [("2000-01-01", None)]
    with pytest.raises(WeatherError):
        fetch(good | {"daily_units": {"temperature_2m_max": "\u00b0F"}})
    with pytest.raises(WeatherError):
        fetch(good | {"daily": {"time": [], "temperature_2m_max": [20]}})
    with pytest.raises(WeatherError):
        fetch({})


def test_retries_server_failure():
    with pytest.raises(WeatherError):
        fetch({}, 503)


def test_timeout_retries(monkeypatch):
    attempts = []

    async def run():
        def handler(request):
            attempts.append(1)
            raise httpx.ReadTimeout("secret upstream details")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await WeatherProvider(client).daily(
                17, 78, date(2000, 1, 1), date(2000, 1, 2)
            )

    with pytest.raises(WeatherError, match="timed out"):
        asyncio.run(run())
    assert len(attempts) == 3
