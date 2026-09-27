"""Vercel ASGI entrypoint for the FastAPI service."""

from backend.app.main import app

__all__ = ["app"]
