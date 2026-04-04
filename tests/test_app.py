import asyncio
import httpx
from httpx import ASGITransport
from app.main import app


def test_health():
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.get("/health"))
    asyncio.run(client.aclose())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_home():
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.get("/"))
    asyncio.run(client.aclose())

    assert response.status_code == 200
    assert "Queue Theory Formula Engine" in response.text
    # Catalog view: carousels and formula cards, no old modals/forms
    assert "carousel-track" in response.text
    assert "formula-card" in response.text
    assert 'id="results-content"' not in response.text
    assert 'id="alerts-content"' not in response.text


def test_detect_candidates():
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    data = {"inputs": {"lambda": 0.5, "mu": 1.0}}
    response = asyncio.run(client.post("/api/detect-candidates", json=data))
    asyncio.run(client.aclose())

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "success"
    assert "candidates" in json_response


def test_detect_candidates_htmx_trigger():
    """HTMX responses must include HX-Trigger header to open result modal."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.post(
        "/api/detect-candidates",
        data={"lambda_": "4", "mu": "5"},
        headers={"HX-Request": "true"},
    ))
    asyncio.run(client.aclose())

    assert response.status_code == 200
    assert response.headers.get("hx-trigger") == "openResultModal"


def test_calculate():
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    data = {"inputs": {"lambda": 0.5, "mu": 1.0}}
    response = asyncio.run(client.post("/api/calculate", json=data))
    asyncio.run(client.aclose())

    assert response.status_code == 200
    json_response = response.json()
    assert "status" in json_response
    assert "messages" in json_response


def test_calculate_htmx_trigger():
    """HTMX calculate responses must include HX-Trigger header."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.post(
        "/api/calculate",
        data={"lambda_": "4", "mu": "5"},
        headers={"HX-Request": "true"},
    ))
    asyncio.run(client.aclose())

    assert response.status_code == 200
    assert response.headers.get("hx-trigger") == "openResultModal"
