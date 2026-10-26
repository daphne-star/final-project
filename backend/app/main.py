"""Ghost Board FastAPI application."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import settings
from app.db.session import engine
from app.orchestration.stream import reconcile_orphaned_meetings
from app.schemas.common import ErrorDetail, ErrorResponse

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger("ghostboard")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Ghost Board starting in %s mode", settings.environment)
    # Meetings run as in-process tasks, so a restart orphans anything that was
    # mid-flight. Mark those failed rather than leaving them stuck at RUNNING.
    try:
        orphaned = await reconcile_orphaned_meetings()
        if orphaned:
            logger.warning("Marked %d orphaned meeting(s) as failed", orphaned)
    except Exception:
        logger.exception("Startup reconciliation failed; continuing")
    yield
    await engine.dispose()
    logger.info("Ghost Board shut down")


app = FastAPI(
    title="Ghost Board API",
    description="AI executive boardroom and strategic advisory platform.",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    docs_url=f"{settings.api_v1_prefix}/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Uniform error envelope so the frontend never has to guess the shape."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorDetail(code=f"http_{exc.status_code}", message=str(exc.detail))
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error=ErrorDetail(
                code="validation_error",
                message="Request validation failed",
                details={"errors": exc.errors()},
            )
        ).model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the detail, return a safe message (spec section 15)."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=ErrorDetail(code="internal_error", message="An internal error occurred")
        ).model_dump(),
    )


app.include_router(api_router, prefix=settings.api_v1_prefix)
