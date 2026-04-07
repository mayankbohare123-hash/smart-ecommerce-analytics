"""
main.py
───────
FastAPI application entry point.

Responsibilities:
  - Creates the FastAPI app instance
  - Registers middleware (CORS, logging, timing)
  - Mounts all API routers
  - Runs startup / shutdown lifecycle hooks
  - Provides health check and root endpoints

Run locally:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Or via the bottom __main__ block:
    python -m app.main
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from loguru import logger
import time
import sys

from app.config import settings
from app.database import create_tables


# ── Logging setup ─────────────────────────────────────────────────────────────
# Remove default handler and replace with structured loguru output
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
    level="DEBUG" if settings.DEBUG else "INFO",
    colorize=True,
)


# ── Lifespan (startup & shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before `yield` runs on startup.
    Code after `yield` runs on shutdown.
    """
    # ── Startup ──
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"   Environment : {settings.APP_ENV}")
    logger.info(f"   Database    : {settings.DATABASE_URL}")
    logger.info(f"   Upload dir  : {settings.upload_dir_path}")

    # Create DB tables if they don't exist
    create_tables()
    logger.info("✅ Database tables ready")

    # Ensure upload and model directories exist
    settings.upload_dir_path   # triggers mkdir inside property
    settings.model_dir_path
    logger.info("✅ Storage directories ready")

    yield  # ← app is running here

    # ── Shutdown ──
    logger.info("👋 Shutting down gracefully")


# ── App factory ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    """
    Factory function that builds and configures the FastAPI app.
    Separating creation from instantiation makes the app testable.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Upload CSV sales data and get analytics, visualizations, and ML-powered predictions.",
        docs_url="/docs" if not settings.is_production else None,    # hide in prod
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware stack (order matters — outermost runs first) ───────────────

    # 1. CORS — allow requests from the frontend dev server and production domain
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. GZip — compress responses > 1KB (helps with large chart data payloads)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Request timing middleware (custom) ────────────────────────────────────
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        """
        Adds an X-Process-Time header to every response.
        Useful for frontend performance monitoring.
        """
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
        logger.debug(f"{request.method} {request.url.path} → {response.status_code} ({duration_ms:.1f}ms)")
        return response

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Catch-all for unhandled exceptions.
        Returns a clean JSON error instead of a raw 500 traceback.
        """
        logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "detail": str(exc) if settings.DEBUG else "Please try again later.",
                "status_code": 500,
            }
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    # Import lazily to avoid circular imports
    from app.routes import upload, analytics, visualize, predict

    API_PREFIX = "/api"

    app.include_router(upload.router,    prefix=API_PREFIX, tags=["Upload"])
    app.include_router(analytics.router, prefix=API_PREFIX, tags=["Analytics"])
    app.include_router(visualize.router, prefix=API_PREFIX, tags=["Visualizations"])
    app.include_router(predict.router,   prefix=API_PREFIX, tags=["Predictions"])

    # ── Static files (uploaded CSVs for direct download, if needed) ───────────
    app.mount(
        "/uploads",
        StaticFiles(directory=str(settings.upload_dir_path), check_dir=False),
        name="uploads",
    )

    # ── Core endpoints ────────────────────────────────────────────────────────

    @app.get("/", tags=["Root"], summary="API root")
    async def root():
        """Welcome endpoint — confirms the API is reachable."""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "docs": "/docs",
            "environment": settings.APP_ENV,
        }

    @app.get("/health", tags=["Health"], summary="Health check")
    async def health_check():
        """
        Health check endpoint used by deployment platforms (Render, Railway)
        and load balancers to confirm the service is alive.
        """
        return {
            "status": "healthy",
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
        }

    return app


# ── App instance ──────────────────────────────────────────────────────────────
# This is what uvicorn imports: `uvicorn app.main:app`
app = create_app()


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,   # auto-reload on file changes in dev
        log_level="debug" if settings.DEBUG else "info",
    )
