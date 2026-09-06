from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import (
    auth,
    balances,
    categories,
    expenses,
    groups,
    reports,
    settlements,
)
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.errors import AppError
from app.repositories import category_repo

logger = logging.getLogger("expense_tracker")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with SessionLocal() as db:
            created = await category_repo.ensure_defaults(db)
            await db.commit()
            if created:
                logger.info("Seeded %s default categories", created)
    except Exception:  # pragma: no cover - seeding must never block startup
        logger.exception("Default category seed skipped")
    yield
    await engine.dispose()


app = FastAPI(
    title="Expense Tracker API",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Explicit origin list, never "*" -- credentials are required for the refresh cookie.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Idempotency-Replayed"],
)


def _envelope(status_code: int, message: str, error_code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "message": message,
            "error_code": error_code,
        },
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _envelope(exc.status_code, exc.message, exc.error_code)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "request"
    return _envelope(422, f"{field}: {first.get('msg', 'is invalid')}", "VALIDATION_ERROR")


@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _envelope(exc.status_code, str(exc.detail), f"HTTP_{exc.status_code}")


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    # Stack traces are logged, never returned (Section 12).
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _envelope(500, "Something went wrong on our end.", "INTERNAL_ERROR")


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"success": True, "data": {"status": "ok"}, "message": None}


API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(groups.router, prefix=API_PREFIX)
app.include_router(expenses.router, prefix=API_PREFIX)
app.include_router(balances.router, prefix=API_PREFIX)
app.include_router(settlements.router, prefix=API_PREFIX)
app.include_router(categories.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)
