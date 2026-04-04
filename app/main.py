from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from presentation.routes import web_router

app = FastAPI(
    title="Queue Theory Formula Engine",
    version="0.1.0",
    description="Base application for a modular queue theory formula engine.",
)

app.mount("/static", StaticFiles(directory="presentation/static"), name="static")
app.include_router(web_router)
