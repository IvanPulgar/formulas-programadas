"""Presentation routes package.

This package exposes FastAPI routers grouped by UI and API concerns.
"""
from .web import router as web_router

__all__ = ["web_router"]
