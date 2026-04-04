import os
import threading
import webbrowser
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from presentation.routes import web_router

load_dotenv()

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
AUTO_OPEN_BROWSER = os.getenv("AUTO_OPEN_BROWSER", "false").lower() == "true"
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

_browser_opened = False


def _open_browser_once():
    global _browser_opened
    if not _browser_opened:
        _browser_opened = True
        webbrowser.open(f"http://{HOST}:{PORT}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if AUTO_OPEN_BROWSER:
        threading.Timer(1.0, _open_browser_once).start()
    yield


app = FastAPI(
    title="Queue Theory Formula Engine",
    version="0.1.0",
    description="Base application for a modular queue theory formula engine.",
    lifespan=lifespan,
)

app.state.demo_mode = DEMO_MODE

app.mount("/static", StaticFiles(directory="presentation/static"), name="static")
app.include_router(web_router)
