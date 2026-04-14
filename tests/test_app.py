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
    # Navigation links present
    assert 'nav-btn' in response.text
    assert 'href="/resolver"' in response.text
    assert 'id="results-content"' not in response.text
    assert 'id="alerts-content"' not in response.text


def test_solver_page():
    """The /resolver page loads with solver cards and carousels."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.get("/resolver"))
    asyncio.run(client.aclose())

    assert response.status_code == 200
    assert "Resolver" in response.text
    assert "solver-card" in response.text
    assert "carousel-track" in response.text
    assert "solver-modal" in response.text
    assert "solver-data" in response.text


def test_solver_page_has_nav():
    """Solver page has navigation buttons with active state."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.get("/resolver"))
    asyncio.run(client.aclose())

    assert 'nav-active' in response.text
    assert 'href="/"' in response.text


def test_solve_success():
    """POST /api/solve/{id} with valid inputs returns success."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.post(
        "/api/solve/pics_rho",
        json={"inputs": {"lambda_": 2, "mu": 5}},
    ))
    asyncio.run(client.aclose())

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["resultVariable"] == "rho"
    assert abs(data["resultValue"] - 0.4) < 1e-6


def test_solve_validation_error():
    """POST /api/solve/{id} rejects invalid inputs (λ ≥ μ for PICS)."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.post(
        "/api/solve/pics_rho",
        json={"inputs": {"lambda_": 10, "mu": 5}},
    ))
    asyncio.run(client.aclose())

    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "error"
    assert "estabilidad" in data["message"].lower()


def test_solve_missing_input():
    """POST /api/solve/{id} rejects missing required inputs."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.post(
        "/api/solve/pics_rho",
        json={"inputs": {"lambda_": 2}},
    ))
    asyncio.run(client.aclose())

    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "error"
    assert "obligatorio" in data["message"].lower()


def test_solve_not_found():
    """POST /api/solve/{id} returns 404 for unknown formula."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.post(
        "/api/solve/nonexistent",
        json={"inputs": {}},
    ))
    asyncio.run(client.aclose())

    assert response.status_code == 404


def test_solve_picm():
    """PICM formula with k servers returns correct result."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.post(
        "/api/solve/picm_stability",
        json={"inputs": {"lambda_": 4, "mu": 3, "k": 2}},
    ))
    asyncio.run(client.aclose())

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert abs(data["resultValue"] - 4 / (2 * 3)) < 1e-6


def test_solve_lq_from_rho_success():
    """POST /api/solve/pics_lq_from_rho with ρ=0.5 → Lq=0.5."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.post(
        "/api/solve/pics_lq_from_rho",
        json={"inputs": {"rho": 0.5}},
    ))
    asyncio.run(client.aclose())

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["formulaId"] == "pics_lq_from_rho"
    assert data["resultVariable"] == "Lq"
    assert abs(data["resultValue"] - 0.5) < 1e-6


def test_solve_lq_from_rho_rejects_rho_one():
    """POST /api/solve/pics_lq_from_rho with ρ=1 → 422."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.post(
        "/api/solve/pics_lq_from_rho",
        json={"inputs": {"rho": 1}},
    ))
    asyncio.run(client.aclose())

    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "error"


def test_solve_lq_from_rho_rejects_rho_zero():
    """POST /api/solve/pics_lq_from_rho with ρ=0 → 422."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.post(
        "/api/solve/pics_lq_from_rho",
        json={"inputs": {"rho": 0}},
    ))
    asyncio.run(client.aclose())

    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "error"


def test_solver_page_contains_lq_from_rho():
    """The /resolver page includes the Lq from rho formula card."""
    transport = ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    response = asyncio.run(client.get("/resolver"))
    asyncio.run(client.aclose())

    assert response.status_code == 200
    assert "pics_lq_from_rho" in response.text


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
