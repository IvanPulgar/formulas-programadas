"""
Tests for GET /analyze — Phase 6.

Covers:
- Route returns 200 HTML
- Page contains the textarea, button and nav link
- Nav bar has all three links ("Catálogo", "Resolver", "Analizar")
- Existing routes (/, /resolver, /health) still return 200
- POST /api/analyze still works (regression from Phase 5)
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestAnalyzePage:
    """GET /analyze — basic render checks."""

    def test_returns_200(self, client):
        response = client.get("/analyze")
        assert response.status_code == 200

    def test_content_type_html(self, client):
        response = client.get("/analyze")
        assert "text/html" in response.headers.get("content-type", "")

    def test_contains_textarea(self, client):
        response = client.get("/analyze")
        assert "<textarea" in response.text

    def test_contains_analyze_button(self, client):
        response = client.get("/analyze")
        assert "Analizar" in response.text

    def test_contains_title(self, client):
        response = client.get("/analyze")
        assert "Queue Theory Formula Engine" in response.text

    def test_contains_result_area(self, client):
        response = client.get("/analyze")
        assert 'id="result-area"' in response.text

    def test_contains_api_fetch_call(self, client):
        """The page must reference /api/analyze in its JS."""
        response = client.get("/analyze")
        assert "/api/analyze" in response.text

    def test_links_to_static_css(self, client):
        response = client.get("/analyze")
        assert "/static/styles.css" in response.text


class TestAnalyzePageNav:
    """Nav bar rendered on /analyze must contain all three links."""

    def test_nav_has_catalog_link(self, client):
        response = client.get("/analyze")
        assert 'href="/"' in response.text

    def test_nav_has_resolver_link(self, client):
        response = client.get("/analyze")
        assert 'href="/resolver"' in response.text

    def test_nav_has_analyze_link(self, client):
        response = client.get("/analyze")
        assert 'href="/analyze"' in response.text

    def test_analyze_link_is_active(self, client):
        """The active class must be applied to the Analizar link on this page."""
        response = client.get("/analyze")
        # The active nav link contains nav-active and the href
        assert "nav-active" in response.text


class TestNavRegressionOtherPages:
    """Pages / and /resolver must still render the updated nav without error."""

    def test_home_still_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_home_has_analyze_link(self, client):
        """After nav.html was modified the new link must appear on / too."""
        response = client.get("/")
        assert 'href="/analyze"' in response.text

    def test_resolver_still_200(self, client):
        response = client.get("/resolver")
        assert response.status_code == 200

    def test_resolver_has_analyze_link(self, client):
        response = client.get("/resolver")
        assert 'href="/analyze"' in response.text

    def test_health_still_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200


class TestAPIRegressionFromPhase5:
    """POST /api/analyze must still work after Phase 6 additions."""

    PICS_TEXT = (
        "Una tienda de alimentacion es atendida por una persona. "
        "Llegan 10 clientes por hora con proceso Poisson. "
        "Tiempo medio de atencion 4 minutos. "
        "Calcular tiempo de espera."
    )

    def test_api_analyze_still_200(self, client):
        response = client.post("/api/analyze", json={"text": self.PICS_TEXT})
        assert response.status_code == 200

    def test_api_analyze_returns_ok(self, client):
        data = client.post("/api/analyze", json={"text": self.PICS_TEXT}).json()
        assert data["ok"] is True

    def test_api_analyze_422_on_short_text(self, client):
        response = client.post("/api/analyze", json={"text": "hi"})
        assert response.status_code == 422
