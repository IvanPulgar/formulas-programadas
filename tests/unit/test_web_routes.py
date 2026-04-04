import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestWebRoutes:
    """Test cases for web routes."""

    def test_home_page(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "Queue Theory Formula Engine" in response.text

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_detect_candidates_api(self, client):
        # Test with minimal inputs
        response = client.post(
            "/api/detect-candidates",
            json={"inputs": {"lambda_": 2.0, "mu": 3.0}}
        )
        assert response.status_code == 200
        data = response.json()
        assert "candidates" in data
        assert isinstance(data["candidates"], list)

    def test_calculate_api(self, client):
        # Test calculation endpoint
        response = client.post(
            "/api/calculate",
            json={"inputs": {"lambda_": 2.0, "mu": 3.0}}
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "messages" in data

    def test_detect_candidates_htmx(self, client):
        # Test HTMX request
        response = client.post(
            "/api/detect-candidates",
            json={"inputs": {"lambda_": 2.0, "mu": 3.0}},
            headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_calculate_htmx(self, client):
        # Test HTMX request
        response = client.post(
            "/api/calculate",
            json={"inputs": {"lambda_": 2.0, "mu": 3.0}},
            headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")