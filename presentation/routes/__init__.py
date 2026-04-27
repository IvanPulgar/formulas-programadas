"""Presentation routes package.

This package exposes FastAPI routers grouped by UI and API concerns.
"""
from .analysis import router as analysis_router
from .web import router as web_router

__all__ = ["web_router", "analysis_router"]
