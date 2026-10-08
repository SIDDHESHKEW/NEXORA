"""FastAPI Application Entry Point for SGSU AI-Native University Platform."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.core.config import settings
from backend.core.db import engine, Base, SessionLocal
from backend.core.logging import setup_logging, TraceIdMiddleware
from backend.core.errors import (
    AppError,
    app_error_handler,
    validation_error_handler,
    http_exception_handler,
)

# Import all SQLAlchemy models to register with Base.metadata
import backend.models  # noqa: F401
from backend.seed.seed_data import seed_database, validate_seed_integrity

# Routers
from backend.modules.auth.routes import router as auth_router
from backend.modules.curriculum.routes import router as curriculum_router
from backend.modules.content.routes import router as content_router
from backend.modules.classroom.routes import router as classroom_router, ws_router
from backend.modules.assessment.routes import router as assessment_router
from backend.modules.student_intel.routes import router as student_intel_router
from backend.modules.teacher_intel.routes import router as teacher_intel_router
from backend.modules.university_intel.routes import router as university_intel_router
from backend.modules.governance.routes import router as governance_router
from backend.modules.demo.routes import router as demo_router

setup_logging()
logger = logging.getLogger("sgsu.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize schema, execute seed, verify integrity."""
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)

    logger.info("Running idempotent seed routine...")
    with SessionLocal() as db:
        seed_database(db)
        integrity = validate_seed_integrity(db)
        if not integrity["healthy"]:
            failed = [k for k, v in integrity["checks"].items() if not v]
            logger.error(f"STARTUP SEED INTEGRITY FAILURE: {failed}")
        else:
            logger.info("Startup seed integrity successfully verified.")

    yield
    logger.info("Application shutting down.")


app = FastAPI(
    title="SGSU AI-Native University Platform — Conference Demonstrator",
    description=(
        "Authoritative backend API for Scope Global Skills University (SGSU). "
        "Implements synchronized classroom, Bayesian mastery estimation, faculty lesson authoring, "
        "and centralized AI Gateway with deterministic fallback."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# 1. Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TraceIdMiddleware)

# 2. Exception Handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)

# 3. Mount Routers
app.include_router(auth_router)
app.include_router(curriculum_router)
app.include_router(content_router)
app.include_router(classroom_router)
app.include_router(assessment_router)
app.include_router(student_intel_router)
app.include_router(teacher_intel_router)
app.include_router(university_intel_router, prefix="/api")
app.include_router(governance_router, prefix="/api")
app.include_router(demo_router, prefix="/api")

# WebSocket routes mounted at root (path: /ws/sessions/{id})
app.include_router(ws_router)


@app.get("/")
def root():
    return {
        "platform": "SGSU AI-Native University Platform",
        "demonstrator": "Conference Showcase MVP",
        "status": "online",
        "docs": "/docs",
    }
