"""Vercel ASGI entrypoint for the FastAPI service."""

import os

# Vercel's writable filesystem is limited to /tmp; the synthetic demo corpus is
# re-ingested on each warm function instance and is intentionally ephemeral.
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/copilot.db")

from backend.app.main import app

__all__ = ["app"]
