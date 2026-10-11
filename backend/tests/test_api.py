from datetime import datetime, timezone
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from app.main import app, clients
from app.services.weather import WeatherError
from app.schemas import AnalysisRequest
from pydantic import ValidationError

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
        {"end_year": datetime.now(timezone.utc).year},
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
    app.state.weather = AsyncMock()
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
        client.get("/api/v1/regions/search?q=x")
    response = client.get("/api/v1/regions/search?q=x")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
