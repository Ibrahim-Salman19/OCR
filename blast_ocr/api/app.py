"""
blast_ocr.api.app

FastAPI Application Entrypoint for B.L.A.S.T. OCR Protocol.
Configures CORS middleware, OpenAPI documentation metadata, request lifecycle,
and registers API routers.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pathlib import Path
import json
import time
import logging

from blast_ocr.api.routes import router as ocr_router

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

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
    """Measures request execution time and adds agent discoverability headers."""
    start_time = time.monotonic()
    response = await call_next(request)
    process_time = time.monotonic() - start_time
    response.headers["X-Process-Time-Sec"] = f"{process_time:.4f}"
    response.headers["X-API-Version"] = "3.0.0"
    response.headers["X-Agent-Discoverable"] = "true"
    response.headers["Link"] = '</llms.txt>; rel="describedby"'
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
        "llms_roadmap": "/llms.txt",
        "llms_full_spec": "/llms-full.txt",
        "health": "/v1/health",
        "metrics": "/v1/metrics",
    }


@app.get("/llms.txt", tags=["AI Agent Discovery"], response_class=PlainTextResponse)
async def get_llms_txt():
    """Returns the llms.txt standard roadmap for AI agents."""
    llms_path = ROOT_DIR / "llms.txt"
    if llms_path.exists():
        return PlainTextResponse(llms_path.read_text(encoding="utf-8"), media_type="text/markdown")
    return PlainTextResponse("# B.L.A.S.T. OCR Engine\n> High-throughput ONNX OCR engine.")


@app.get("/llms-full.txt", tags=["AI Agent Discovery"], response_class=PlainTextResponse)
async def get_llms_full_txt():
    """Returns the full unified specification for single-prompt LLM ingestion."""
    llms_full_path = ROOT_DIR / "llms-full.txt"
    if llms_full_path.exists():
        return PlainTextResponse(llms_full_path.read_text(encoding="utf-8"), media_type="text/markdown")
    return PlainTextResponse("# B.L.A.S.T. OCR Engine Specification")


@app.get("/robots.txt", tags=["Search Engines"], response_class=PlainTextResponse)
async def get_robots_txt():
    """Returns robots.txt crawling directives."""
    robots_path = ROOT_DIR / "robots.txt"
    if robots_path.exists():
        return PlainTextResponse(robots_path.read_text(encoding="utf-8"), media_type="text/plain")
    return PlainTextResponse("User-agent: *\nAllow: /\n")


@app.get("/sitemap.xml", tags=["Search Engines"])
async def get_sitemap_xml():
    """Returns sitemap.xml for search engine indexing."""
    sitemap_path = ROOT_DIR / "sitemap.xml"
    if sitemap_path.exists():
        return Response(content=sitemap_path.read_text(encoding="utf-8"), media_type="application/xml")
    return Response(content="<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'></urlset>", media_type="application/xml")


@app.get("/.well-known/ai-plugin.json", tags=["AI Agent Discovery"])
async def get_ai_plugin():
    """Returns AI plugin manifest for OpenAI/ChatGPT actions."""
    plugin_path = ROOT_DIR / ".well-known" / "ai-plugin.json"
    if plugin_path.exists():
        return json.loads(plugin_path.read_text(encoding="utf-8"))
    return {"name_for_model": "blast_ocr", "description_for_model": "B.L.A.S.T. OCR Engine"}
