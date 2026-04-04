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


class TestFormDataFlow:
    """Tests for HTMX form-encoded data submissions (real browser flow)."""

    def test_detect_candidates_form_data(self, client):
        response = client.post(
            "/api/detect-candidates",
            data={"lambda_": "2.0", "mu": "3.0"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_calculate_form_data(self, client):
        response = client.post(
            "/api/calculate",
            data={"lambda_": "2.0", "mu": "3.0", "category": "PICS"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_calculate_form_data_with_selected_formula(self, client):
        response = client.post(
            "/api/calculate",
            data={"lambda_": "2.0", "mu": "3.0", "selected_formula_id": "pics_rho", "category": "PICS"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Cálculo Exitoso" in response.text

    def test_calculate_form_data_empty_values_skipped(self, client):
        response = client.post(
            "/api/calculate",
            data={"lambda_": "2.0", "mu": "3.0", "rho": "", "category": "PICS"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200

    def test_modal_endpoint_loads(self, client):
        response = client.get("/api/formula-modal/pics_rho")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "pics_rho" in response.text or "rho" in response.text.lower()

    def test_modal_endpoint_not_found(self, client):
        response = client.get("/api/formula-modal/nonexistent_formula")
        assert response.status_code == 404


class TestOrchestratorIntegration:
    """End-to-end orchestrator tests verifying normalization → resolution → matching → solving."""

    def test_orchestrator_direct_calculation(self, client):
        response = client.post(
            "/api/calculate",
            json={"inputs": {"lambda_": 2.0, "mu": 3.0}, "selected_formula_id": "pics_rho"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert abs(data["computed_value"] - 0.6667) < 0.01

    def test_orchestrator_validation_mode(self, client):
        response = client.post(
            "/api/calculate",
            json={"inputs": {"lambda_": 2.0, "mu": 3.0, "rho": 0.6667}, "selected_formula_id": "pics_rho"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["validation_result"] is not None

    def test_orchestrator_auto_matching(self, client):
        response = client.post(
            "/api/calculate",
            json={"inputs": {"lambda_": 2.0, "mu": 3.0}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"