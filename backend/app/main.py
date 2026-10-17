"""
main.py — UPDATED: added auth router.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from loguru import logger
import time, sys

from app.config import settings
from app.database import create_tables

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
    level="DEBUG" if settings.DEBUG else "INFO",
    colorize=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"   Environment : {settings.APP_ENV}")
    logger.info(f"   Database    : {settings.DATABASE_URL}")
    create_tables()
    logger.info("✅ Database tables ready (including users table)")
    settings.upload_dir_path
    settings.model_dir_path
    logger.info("✅ Storage directories ready")
    yield
    logger.info("👋 Shutting down gracefully")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="SalesIQ — Upload CSV sales data and get analytics, visualizations, and ML predictions.",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
        logger.debug(f"{request.method} {request.url.path} → {response.status_code} ({duration_ms:.1f}ms)")
        return response

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(status_code=500, content={
            "success": False, "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "Please try again later.",
            "status_code": 500,
        })

    # ── Routers ───────────────────────────────────────────────
    from app.routes import auth, upload, analytics, visualize, predict

    API_PREFIX = "/api"
    app.include_router(auth.router,      prefix=API_PREFIX, tags=["Authentication"])
    app.include_router(upload.router,    prefix=API_PREFIX, tags=["Upload"])
    app.include_router(analytics.router, prefix=API_PREFIX, tags=["Analytics"])
    app.include_router(visualize.router, prefix=API_PREFIX, tags=["Visualizations"])
    app.include_router(predict.router,   prefix=API_PREFIX, tags=["Predictions"])

    app.mount("/uploads", StaticFiles(directory=str(settings.upload_dir_path), check_dir=False), name="uploads")

    @app.get("/", tags=["Root"])
    async def root():
        return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running", "docs": "/docs"}

    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "version": settings.APP_VERSION}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
