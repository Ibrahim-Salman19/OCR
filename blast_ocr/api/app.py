"""
blast_ocr.api.app

FastAPI Application Entrypoint for B.L.A.S.T. OCR Protocol.
Configures CORS middleware, OpenAPI documentation metadata, request lifecycle,
and registers API routers.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from blast_ocr.api.routes import router as ocr_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="B.L.A.S.T. OCR Engine - Enterprise REST API",
    description=(
        "Production-grade Deterministic Document Intelligence and OCR Automation API. "
        "Transforms scanned PDFs, PPTX, and image documents into Searchable PDFs, "
        "Markdown (with Frontmatter), styled DOCX, EPUB 3.0, and structured JSON models."
    ),
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Measures request execution time and adds latency headers."""
    start_time = time.monotonic()
    response = await call_next(request)
    process_time = time.monotonic() - start_time
    response.headers["X-Process-Time-Sec"] = f"{process_time:.4f}"
    response.headers["X-API-Version"] = "3.0.0"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catches unhandled server exceptions and returns structured JSON responses."""
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "path": request.url.path,
        },
    )


# Register API routes
app.include_router(ocr_router)


@app.get("/", tags=["General"])
async def root():
    """Root entrypoint returning system identity and documentation links."""
    return {
        "name": "B.L.A.S.T. OCR Engine",
        "version": "3.0.0",
        "status": "operational",
        "documentation": "/docs",
        "openapi_schema": "/openapi.json",
        "health": "/v1/health",
        "metrics": "/v1/metrics",
    }
