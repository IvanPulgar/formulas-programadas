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
