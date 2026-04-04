from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from presentation.schemas.health import HealthResponse

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request, "title": "Queue Theory Formula Engine"},
    )


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
