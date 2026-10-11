from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app, clients
from app.schemas import AnalysisRequest
from app.services.weather import WeatherError

VALID = {"latitude": 17.385, "longitude": 78.4867, "start_year": 1990, "end_year": 2020}


@pytest.mark.parametrize(
    "override",
    [
        {"latitude": 91},
        {"longitude": -181},
        {"latitude": float("nan")},
        {"start_year": 2021, "end_year": 2020},
        {"start_year": 1939},
        {"start_year": 1940, "end_year": 2020},
        {"start_year": "1990"},
        {"end_year": datetime.now(UTC).year},
        {"hazard": "drought"},
        {"extra": 1},
    ],
)
def test_invalid_inputs(override):
    with pytest.raises(ValidationError):
        AnalysisRequest(**(VALID | override))


@pytest.fixture
def client():
    clients.clear()
    app.state.analysis = AsyncMock()
    app.state.analysis.execute.return_value = {"ok": True}
    app.state.weather = AsyncMock()
    app.state.weather.search.return_value = []
    return TestClient(app)


def test_health_and_validation(client):
    assert client.get("/api/v1/health").status_code == 200
    assert (
        client.post("/api/v1/analyze", json=VALID | {"latitude": 99}).status_code == 422
    )


def test_upstream_failure(client):
    app.state.analysis.execute.side_effect = WeatherError(
        "Weather provider is unavailable or timed out"
    )
    response = client.post("/api/v1/analyze", json=VALID)
    assert response.status_code == 502
    assert "timed out" in response.json()["detail"]


def test_body_limit(client):
    assert client.post("/api/v1/analyze", content="x" * 4097).status_code == 413


def test_rate_limit(client):
    for _ in range(20):
        client.post("/api/v1/analyze", json=VALID)
    response = client.post("/api/v1/analyze", json=VALID)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    # Typing in city search must not consume the analysis budget, or vice versa.
    assert client.get("/api/v1/regions/search?q=hy").status_code == 200


def test_search_has_its_own_larger_budget(client):
    codes = [client.get("/api/v1/regions/search?q=hy").status_code for _ in range(61)]
    assert codes[:60] == [200] * 60
    assert codes[60] == 429


def test_forwarded_for_uses_only_proxy_appended_address(client, monkeypatch):
    from app.main import settings

    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    for i in range(20):
        # A client rotating a spoofed left-hand value must still share one bucket.
        client.post(
            "/api/v1/analyze",
            json=VALID,
            headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"},
        )
    blocked = client.post(
        "/api/v1/analyze",
        json=VALID,
        headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.7"},
    )
    assert blocked.status_code == 429
    other = client.post(
        "/api/v1/analyze", json=VALID, headers={"X-Forwarded-For": "198.51.100.1"}
    )
    assert other.status_code != 429


def test_coordinates_are_rounded_for_cache_keys():
    request = AnalysisRequest(**(VALID | {"latitude": 17.38512, "longitude": 78.48671}))
    assert (request.latitude, request.longitude) == (17.39, 78.49)


def test_overflowing_number_is_a_clean_422(client):
    response = client.post(
        "/api/v1/analyze",
        content='{"latitude":1e999,"longitude":0,"start_year":1990,"end_year":2000}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert "input" not in response.json()["detail"][0]
