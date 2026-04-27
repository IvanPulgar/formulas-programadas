"""
Tests for hint_model support — Phase 7A.

Scenarios covered:
  API validation:
    - hint_model absent → behaves as before (no regression)
    - hint_model valid values → accepted (200)
    - hint_model invalid value → 422
    - hint_model null explicitly → accepted (200, treated as absent)

  Analyzer behavior:
    - hint_model matches auto-detected model → no override issue
    - hint_model differs from auto-detected → override INFO issue emitted
    - hint_model provided when auto-detection fails (gibberish) → fallback INFO issue
    - hint_model None, auto-detection fails → model_id remains None

  Full pipeline with hint:
    - Gibberish text + hint_model="PICS" → pipeline can run with manual variables
    - PICS text + hint_model="PICM" → model forced to PICM
    - PICS text + no hint → model_id="PICS" (regression guard)

  UI page:
    - /analyze page contains the <select> element
    - Option values match valid model IDs
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from domain.entities.analysis import StatementAnalysisRequest
from domain.services.statement_analyzer import make_analyzer


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


PICS_TEXT = (
    "Una tienda de alimentacion es atendida por una persona. "
    "Llegan 10 clientes por hora con proceso Poisson. "
    "Tiempo medio de atencion 4 minutos. "
    "Calcular tiempo de espera."
)

GIBBERISH_TEXT = "El gato comio la sopa con mucha rapidez ayer por la tarde."


# ---------------------------------------------------------------------------
# API schema validation
# ---------------------------------------------------------------------------


class TestHintModelSchemaValidation:
    def test_no_hint_model_still_200(self, client):
        response = client.post("/api/analyze", json={"text": PICS_TEXT})
        assert response.status_code == 200

    def test_hint_model_null_accepted(self, client):
        response = client.post("/api/analyze", json={"text": PICS_TEXT, "hint_model": None})
        assert response.status_code == 200

    @pytest.mark.parametrize("model", ["PICS", "PICM", "PFCS", "PFCM", "PFHET"])
    def test_valid_hint_model_accepted(self, client, model):
        response = client.post("/api/analyze", json={"text": PICS_TEXT, "hint_model": model})
        assert response.status_code == 200

    def test_invalid_hint_model_returns_422(self, client):
        response = client.post("/api/analyze", json={"text": PICS_TEXT, "hint_model": "INVALID"})
        assert response.status_code == 422

    def test_lowercase_hint_model_returns_422(self, client):
        """Model IDs are uppercase; lowercase must be rejected."""
        response = client.post("/api/analyze", json={"text": PICS_TEXT, "hint_model": "pics"})
        assert response.status_code == 422

    def test_numeric_hint_model_returns_422(self, client):
        response = client.post("/api/analyze", json={"text": PICS_TEXT, "hint_model": 42})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Analyzer unit tests — hint_model behavior
# ---------------------------------------------------------------------------


class TestAnalyzerHintModelBehavior:
    @pytest.fixture(scope="class")
    def analyzer(self):
        return make_analyzer()

    def test_no_hint_no_change(self, analyzer):
        """Without hint, PICS text → PICS auto-detected."""
        req = StatementAnalysisRequest(text=PICS_TEXT)
        result = analyzer.analyze(req)
        assert result.identified_model == "PICS"
        # No hint-related issues
        codes = [i.code for i in result.issues]
        assert "hint_model_used" not in codes
        assert "hint_model_override" not in codes

    def test_hint_matches_auto_no_issue(self, analyzer):
        """hint_model == auto-detected → no override issue, confidence unchanged."""
        req = StatementAnalysisRequest(text=PICS_TEXT, hint_model="PICS")
        result = analyzer.analyze(req)
        assert result.identified_model == "PICS"
        codes = [i.code for i in result.issues]
        assert "hint_model_override" not in codes

    def test_hint_overrides_auto_detected(self, analyzer):
        """hint_model != auto-detected → model forced to hint, override INFO emitted."""
        req = StatementAnalysisRequest(text=PICS_TEXT, hint_model="PICM")
        result = analyzer.analyze(req)
        assert result.identified_model == "PICM"
        codes = [i.code for i in result.issues]
        assert "hint_model_override" in codes

    def test_hint_override_confidence_is_medium(self, analyzer):
        """Confidence is conservative (MEDIUM) when overriding auto-detection."""
        from domain.entities.analysis import AnalysisConfidence
        req = StatementAnalysisRequest(text=PICS_TEXT, hint_model="PICM")
        result = analyzer.analyze(req)
        assert result.model_confidence == AnalysisConfidence.MEDIUM

    def test_hint_fallback_on_gibberish(self, analyzer):
        """When auto-detection fails, hint_model acts as fallback."""
        req = StatementAnalysisRequest(text=GIBBERISH_TEXT, hint_model="PFCS")
        result = analyzer.analyze(req)
        assert result.identified_model == "PFCS"
        codes = [i.code for i in result.issues]
        assert "hint_model_used" in codes

    def test_hint_fallback_confidence_is_low(self, analyzer):
        """Fallback confidence is LOW (weaker than MEDIUM override)."""
        from domain.entities.analysis import AnalysisConfidence
        req = StatementAnalysisRequest(text=GIBBERISH_TEXT, hint_model="PFCS")
        result = analyzer.analyze(req)
        assert result.model_confidence == AnalysisConfidence.LOW

    def test_no_hint_gibberish_model_is_none(self, analyzer):
        """Without hint and no auto-detection → model_id remains None."""
        req = StatementAnalysisRequest(text=GIBBERISH_TEXT)
        result = analyzer.analyze(req)
        assert result.identified_model is None

    def test_hint_model_none_no_issue(self, analyzer):
        """Explicit hint_model=None behaves identically to not passing hint."""
        req_explicit = StatementAnalysisRequest(text=PICS_TEXT, hint_model=None)
        req_default = StatementAnalysisRequest(text=PICS_TEXT)
        r1 = analyzer.analyze(req_explicit)
        r2 = analyzer.analyze(req_default)
        assert r1.identified_model == r2.identified_model
        assert r1.model_confidence == r2.model_confidence


# ---------------------------------------------------------------------------
# API response with hint_model
# ---------------------------------------------------------------------------


class TestAPIWithHintModel:
    def test_pics_text_no_hint_model_id_pics(self, client):
        data = client.post("/api/analyze", json={"text": PICS_TEXT}).json()
        assert data["model_id"] == "PICS"

    def test_pics_text_hint_picm_overrides(self, client):
        data = client.post(
            "/api/analyze",
            json={"text": PICS_TEXT, "hint_model": "PICM"},
        ).json()
        assert data["model_id"] == "PICM"

    def test_hint_override_emits_info_issue(self, client):
        data = client.post(
            "/api/analyze",
            json={"text": PICS_TEXT, "hint_model": "PICM"},
        ).json()
        joined = " ".join(data["issues"])
        assert "hint_model_override" in joined or "sobreescribe" in joined

    def test_pics_text_hint_pics_no_override_issue(self, client):
        """Hint matches auto-detected → no override info in issues."""
        data = client.post(
            "/api/analyze",
            json={"text": PICS_TEXT, "hint_model": "PICS"},
        ).json()
        joined = " ".join(data["issues"])
        assert "sobreescribe" not in joined

    def test_hint_model_reflected_in_response_model_id(self, client):
        """model_id in response must equal the forced hint."""
        for model in ["PFCS", "PFCM", "PFHET"]:
            data = client.post(
                "/api/analyze",
                json={"text": PICS_TEXT, "hint_model": model},
            ).json()
            assert data["model_id"] == model, f"Expected {model}, got {data['model_id']}"


# ---------------------------------------------------------------------------
# UI page — select element present
# ---------------------------------------------------------------------------


class TestAnalyzePageSelectElement:
    def test_select_present(self, client):
        response = client.get("/analyze")
        assert '<select' in response.text

    def test_select_id(self, client):
        response = client.get("/analyze")
        assert 'id="hint-model-select"' in response.text

    def test_option_pics_present(self, client):
        response = client.get("/analyze")
        assert 'value="PICS"' in response.text

    def test_option_picm_present(self, client):
        response = client.get("/analyze")
        assert 'value="PICM"' in response.text

    def test_option_pfcs_present(self, client):
        response = client.get("/analyze")
        assert 'value="PFCS"' in response.text

    def test_option_pfcm_present(self, client):
        response = client.get("/analyze")
        assert 'value="PFCM"' in response.text

    def test_option_pfhet_present(self, client):
        response = client.get("/analyze")
        assert 'value="PFHET"' in response.text

    def test_empty_default_option_present(self, client):
        """Default option must have empty value (auto-detect)."""
        response = client.get("/analyze")
        assert 'value=""' in response.text

    def test_payload_includes_hint_model_in_js(self, client):
        """The JS fetch call must reference hint_model."""
        response = client.get("/analyze")
        assert "hint_model" in response.text
