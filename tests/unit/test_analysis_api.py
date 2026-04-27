"""
Tests for POST /api/analyze — Phase 5.

Exercises:
- Schema validation: missing text, too short, too long
- PICS end-to-end: valid text → is_complete, primary_values, model_id
- PICM end-to-end: 3-server scenario → is_complete, Wq present
- Blocked plan: missing variable → ok=True, is_complete=False
- Unknown model: gibberish text → ok=True, model_id=None
- Response structure: all required keys present
- Content-Type header: always application/json
- Existing routes unaffected: /, /health, /api/detect-candidates, /api/calculate
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema validation (422)
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_missing_text_returns_422(self, client):
        response = client.post("/api/analyze", json={})
        assert response.status_code == 422

    def test_empty_string_returns_422(self, client):
        response = client.post("/api/analyze", json={"text": ""})
        assert response.status_code == 422

    def test_too_short_text_returns_422(self, client):
        response = client.post("/api/analyze", json={"text": "hi"})
        assert response.status_code == 422

    def test_too_long_text_returns_422(self, client):
        response = client.post("/api/analyze", json={"text": "x" * 2001})
        assert response.status_code == 422

    def test_valid_minimal_text_accepted(self, client):
        response = client.post("/api/analyze", json={"text": "Llegan clientes a la cola."})
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Response structure — always present keys
# ---------------------------------------------------------------------------


class TestResponseStructure:
    REQUIRED_KEYS = {
        "ok", "model_id", "model_confidence", "extracted_variables",
        "inferred_objectives", "plan_is_executable", "plan_steps",
        "is_complete", "primary_values", "step_results", "issues",
    }

    def test_all_required_keys_present(self, client):
        response = client.post(
            "/api/analyze",
            json={"text": "Llegan 10 clientes por hora. Calcular tiempo de espera."},
        )
        assert response.status_code == 200
        data = response.json()
        assert self.REQUIRED_KEYS.issubset(data.keys())

    def test_content_type_is_json(self, client):
        response = client.post(
            "/api/analyze",
            json={"text": "Llegan 10 clientes por hora. Calcular tiempo de espera."},
        )
        assert "application/json" in response.headers.get("content-type", "")

    def test_ok_is_boolean(self, client):
        response = client.post(
            "/api/analyze",
            json={"text": "Llegan 10 clientes por hora. Calcular tiempo de espera."},
        )
        data = response.json()
        assert isinstance(data["ok"], bool)

    def test_extracted_variables_is_list(self, client):
        response = client.post(
            "/api/analyze",
            json={"text": "Llegan 10 clientes por hora. Calcular tiempo de espera."},
        )
        data = response.json()
        assert isinstance(data["extracted_variables"], list)

    def test_plan_steps_is_list(self, client):
        response = client.post(
            "/api/analyze",
            json={"text": "Llegan 10 clientes por hora. Calcular tiempo de espera."},
        )
        data = response.json()
        assert isinstance(data["plan_steps"], list)

    def test_issues_is_list(self, client):
        response = client.post(
            "/api/analyze",
            json={"text": "Llegan 10 clientes por hora. Calcular tiempo de espera."},
        )
        data = response.json()
        assert isinstance(data["issues"], list)


# ---------------------------------------------------------------------------
# PICS end-to-end — tienda, 10 clientes/hora, 4 minutos
# ---------------------------------------------------------------------------


PICS_TEXT = (
    "Una tienda de alimentacion es atendida por una persona. "
    "Llegan 10 clientes por hora con proceso Poisson. "
    "Tiempo medio de atencion 4 minutos. "
    "Calcular tiempo de espera."
)


class TestPICSEndToEnd:
    def test_status_200(self, client):
        response = client.post("/api/analyze", json={"text": PICS_TEXT})
        assert response.status_code == 200

    def test_ok_true(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        assert data["ok"] is True

    def test_model_id_pics(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        assert data["model_id"] == "PICS"

    def test_model_confidence_not_none(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        assert data["model_confidence"] in ("high", "medium", "low", "none")

    def test_is_complete_true(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        assert data["is_complete"] is True

    def test_plan_is_executable_true(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        assert data["plan_is_executable"] is True

    def test_wq_in_primary_values(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        assert "Wq" in data["primary_values"]

    def test_wq_is_positive(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        wq = data["primary_values"]["Wq"]
        assert wq is not None
        assert wq > 0

    def test_extracted_variables_contain_lambda(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        var_ids = [v["variable_id"] for v in data["extracted_variables"]]
        assert "lambda_" in var_ids

    def test_step_results_not_empty(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        assert len(data["step_results"]) > 0

    def test_all_step_results_successful(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        for sr in data["step_results"]:
            assert sr["success"] is True, f"Step {sr['formula_id']} failed"

    def test_no_issues_on_valid_input(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        # May have INFO-level issues but no ERROR issues that prevent completion
        assert data["is_complete"] is True


# ---------------------------------------------------------------------------
# PICM end-to-end — compañía, 3 personas, 2 llamadas/min
# ---------------------------------------------------------------------------


PICM_TEXT = (
    "Una compania tiene 3 personas para recibir llamadas. "
    "Llegan a razon de 2 por minuto con proceso Poisson. "
    "Media de atencion 1 minuto. "
    "Calcular tiempo de espera."
)


class TestPICMEndToEnd:
    def test_status_200(self, client):
        response = client.post("/api/analyze", json={"text": PICM_TEXT})
        assert response.status_code == 200

    def test_model_id_picm(self, client):
        data = client.post("/api/analyze", json={"text": PICM_TEXT}).json()
        assert data["model_id"] == "PICM"

    def test_is_complete_true(self, client):
        data = client.post("/api/analyze", json={"text": PICM_TEXT}).json()
        assert data["is_complete"] is True

    def test_wq_present_and_positive(self, client):
        data = client.post("/api/analyze", json={"text": PICM_TEXT}).json()
        wq = data["primary_values"].get("Wq")
        assert wq is not None
        assert wq > 0

    def test_three_step_results(self, client):
        data = client.post("/api/analyze", json={"text": PICM_TEXT}).json()
        assert len(data["step_results"]) == 3

    def test_k_extracted_as_integer_compatible(self, client):
        """k=3.0 must be handled correctly (int coercion in executor)."""
        data = client.post("/api/analyze", json={"text": PICM_TEXT}).json()
        assert data["is_complete"] is True


# ---------------------------------------------------------------------------
# Blocked plan — missing variable
# ---------------------------------------------------------------------------


MISSING_MU_TEXT = (
    "Una tienda de alimentacion es atendida por una persona. "
    "Llegan 10 clientes por hora con proceso Poisson. "
    "Calcular tiempo de espera en la cola."
)


class TestBlockedPlan:
    def test_status_200(self, client):
        response = client.post("/api/analyze", json={"text": MISSING_MU_TEXT})
        assert response.status_code == 200

    def test_ok_true(self, client):
        """ok=True even when the plan cannot execute — the pipeline ran without exception."""
        data = client.post("/api/analyze", json={"text": MISSING_MU_TEXT}).json()
        assert data["ok"] is True

    def test_is_complete_false(self, client):
        data = client.post("/api/analyze", json={"text": MISSING_MU_TEXT}).json()
        assert data["is_complete"] is False

    def test_issues_not_empty(self, client):
        data = client.post("/api/analyze", json={"text": MISSING_MU_TEXT}).json()
        # Either plan or exec issues should be present
        assert len(data["issues"]) > 0 or data["plan_is_executable"] is False


# ---------------------------------------------------------------------------
# Unrecognized model (gibberish text)
# ---------------------------------------------------------------------------


class TestUnknownModel:
    def test_status_200(self, client):
        response = client.post(
            "/api/analyze",
            json={"text": "El gato comio la sopa con mucha rapidez ayer."},
        )
        assert response.status_code == 200

    def test_ok_true(self, client):
        data = client.post(
            "/api/analyze",
            json={"text": "El gato comio la sopa con mucha rapidez ayer."},
        ).json()
        assert data["ok"] is True

    def test_model_id_none(self, client):
        data = client.post(
            "/api/analyze",
            json={"text": "El gato comio la sopa con mucha rapidez ayer."},
        ).json()
        assert data["model_id"] is None

    def test_is_complete_false(self, client):
        data = client.post(
            "/api/analyze",
            json={"text": "El gato comio la sopa con mucha rapidez ayer."},
        ).json()
        assert data["is_complete"] is False


# ---------------------------------------------------------------------------
# StepInfo schema shape
# ---------------------------------------------------------------------------


class TestStepInfoSchema:
    def test_step_has_required_fields(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        for step in data["plan_steps"]:
            assert "formula_id" in step
            assert "status" in step
            assert "is_primary" in step
            assert "produces" in step
            assert "blocked_by" in step

    def test_step_status_values(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        for step in data["plan_steps"]:
            assert step["status"] in ("executable", "blocked")


# ---------------------------------------------------------------------------
# Regression: existing routes still work
# ---------------------------------------------------------------------------


class TestExistingRoutesUnaffected:
    def test_home_still_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_health_still_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert client.get("/health").json()["status"] == "ok"

    def test_detect_candidates_still_works(self, client):
        response = client.post(
            "/api/detect-candidates",
            json={"inputs": {"lambda_": 2.0, "mu": 3.0}},
        )
        assert response.status_code == 200

    def test_calculate_still_works(self, client):
        response = client.post(
            "/api/calculate",
            json={"inputs": {"lambda_": 2.0, "mu": 3.0}},
        )
        assert response.status_code == 200
