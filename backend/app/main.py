import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes import router
from backend.app.core.config import Settings
from backend.app.observability.telemetry import setup_telemetry
from backend.app.service import RagService

logger = logging.getLogger("copilot.api")


def create_app(settings: Settings | None = None, service: RagService | None = None) -> FastAPI:
    configuration = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.service = service or RagService(configuration)
        setup_telemetry(configuration)
        if configuration.auto_ingest and not app.state.service.index_compatible():
            app.state.service.ingest()
        yield
        if service is None:
            app.state.service.db.engine.dispose()

    app = FastAPI(title="Enterprise Financial Knowledge Copilot", version="0.1.0",
                  description="Synthetic financial-policy RAG. Demo role headers are not production authentication.",
                  lifespan=lifespan)
    app.state.settings = configuration
    app.add_middleware(CORSMiddleware, allow_origins=configuration.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization", "X-Demo-Role"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        # No exception message or request body is logged; upstream payloads may contain confidential data.
        logger.error("request_failure exception_type=%s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "financial-knowledge-copilot"}

    @app.get("/ready")
    def ready(request: Request):
        rag = request.app.state.service
        try:
            healthy = rag.db.ready() and rag.index_compatible() and rag.chunk_count() > 0
        except Exception:
            healthy = False
        return JSONResponse(status_code=200 if healthy else 503,
                            content={"status": "ready" if healthy else "not_ready",
                                     "checks": {"database_and_index": healthy}})

    app.include_router(router)
    return app


app = create_app()
