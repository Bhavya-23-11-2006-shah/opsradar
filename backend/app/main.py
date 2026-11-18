"""OpsRadar API entrypoint: uvicorn app.main:app --reload"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import db
from .api import actions, analysis, demo, findings, health, overview, quality, report, upload
from .config import CORS_ORIGINS
from .llm import client as llm_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("opsradar")

ERROR_SLUGS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    500: "internal_error",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    logger.info("OpsRadar API ready (contract v1, llm mode=%s)", llm_client.mode)
    yield


app = FastAPI(
    title="OpsRadar API",
    description="AI-powered operational intelligence & early warning system (contract v1).",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    error = ERROR_SLUGS.get(exc.status_code, "request_failed")
    detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, default=str)
    return JSONResponse(status_code=exc.status_code, content={"error": error, "detail": detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    detail = json.dumps(exc.errors(), default=str)
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "detail": detail[:2000]},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": f"{exc.__class__.__name__}: {exc}"},
    )


for router in (
    health.router,
    demo.router,
    upload.router,
    analysis.router,
    quality.router,
    overview.router,
    findings.router,
    actions.router,
    report.router,
):
    app.include_router(router)
