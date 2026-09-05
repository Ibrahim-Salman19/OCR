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
    """Measures request execution time and adds agent discoverability & SEO headers."""
    start_time = time.monotonic()
    response = await call_next(request)
    process_time = time.monotonic() - start_time
    response.headers["X-Process-Time-Sec"] = f"{process_time:.4f}"
    response.headers["X-API-Version"] = "3.0.0"
    response.headers["X-Agent-Discoverable"] = "true"
    response.headers["X-Robots-Tag"] = "all, index, follow"
    response.headers["X-Model-Context-Protocol"] = "/mcp.json"
    response.headers["Link"] = '</llms.txt>; rel="describedby", </llms-full.txt>; rel="alternate"; type="text/markdown"'
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
    """Root entrypoint returning system identity, documentation, and agent discovery links."""
    return {
        "name": "B.L.A.S.T. OCR Engine",
        "version": "3.0.0",
        "status": "operational",
        "documentation": "/docs",
        "openapi_schema": "/openapi.json",
        "llms_roadmap": "/llms.txt",
        "llms_full_spec": "/llms-full.txt",
        "mcp_manifest": "/mcp.json",
        "schema_jsonld": "/v1/schema.json",
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


@app.get("/mcp.json", tags=["AI Agent Discovery"])
@app.get("/.well-known/mcp.json", tags=["AI Agent Discovery"])
async def get_mcp_manifest():
    """Returns Model Context Protocol (MCP) server manifest."""
    mcp_path = ROOT_DIR / "mcp.json"
    if mcp_path.exists():
        return json.loads(mcp_path.read_text(encoding="utf-8"))
    return {"mcpServers": {"blast-ocr": {"command": "python3", "args": ["-m", "blast_ocr.mcp_server"]}}}


@app.get("/.well-known/ai-plugin.json", tags=["AI Agent Discovery"])
async def get_ai_plugin():
    """Returns AI plugin manifest for OpenAI/ChatGPT actions."""
    plugin_path = ROOT_DIR / ".well-known" / "ai-plugin.json"
    if plugin_path.exists():
        return json.loads(plugin_path.read_text(encoding="utf-8"))
    return {"name_for_model": "blast_ocr", "description_for_model": "B.L.A.S.T. OCR Engine"}


@app.get("/v1/schema.json", tags=["Search Engines & SEO"])
async def get_schema_jsonld():
    """Returns official Schema.org JSON-LD graph describing B.L.A.S.T. OCR."""
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "@id": "https://github.com/Ibrahim-Salman19/OCR#software",
                "name": "B.L.A.S.T. OCR Engine",
                "alternateName": "BLAST OCR",
                "description": "Self-hosted OCR and document intelligence engine with ONNX Runtime multi-provider acceleration, bounded streaming memory, table extraction, and native AI Agent MCP integration.",
                "applicationCategory": "DeveloperApplication",
                "operatingSystem": "Linux, Windows, macOS",
                "softwareVersion": "3.0.0",
                "downloadUrl": "https://github.com/Ibrahim-Salman19/OCR",
                "installUrl": "https://github.com/Ibrahim-Salman19/OCR/blob/main/docs/DEPLOYMENT_GUIDE.md",
                "license": "https://opensource.org/licenses/MIT",
                "author": {"@id": "https://ibrahimsalman.vercel.app/#person"},
                "creator": {"@id": "https://ibrahimsalman.vercel.app/#person"},
                "offers": {
                    "@type": "Offer",
                    "price": "0",
                    "priceCurrency": "USD",
                },
                "featureList": [
                    "ONNX Runtime multi-provider acceleration (CUDA, DirectML, CPU)",
                    "Table structure extraction to Markdown and HTML with a built-in TEDS evaluator",
                    "LaTeX Mathematical Formula Recognition (inline and display)",
                    "Bounded streaming memory architecture (0.0002 MB/page growth slope, measured)",
                    "Dual-Layer Selectable Sandwich PDF Generation",
                    "Native Model Context Protocol (MCP) Server for AI Agents",
                    "LangChain and LlamaIndex Document Loaders",
                    "Forensic 8-Class PII Redaction",
                    "Distributed 3-Tier Priority Queue Swarm with Heartbeats and Zombie Reaper",
                ],
            },
            {
                "@type": "SoftwareSourceCode",
                "@id": "https://github.com/Ibrahim-Salman19/OCR#sourcecode",
                "name": "B.L.A.S.T. OCR Source Code",
                "programmingLanguage": "Python",
                "runtimePlatform": "Python 3.9, 3.10, 3.11, 3.12, 3.13",
                "codeRepository": "https://github.com/Ibrahim-Salman19/OCR",
                "license": "https://opensource.org/licenses/MIT",
                "author": {"@id": "https://ibrahimsalman.vercel.app/#person"},
            },
            {
                "@type": "TechArticle",
                "@id": "https://github.com/Ibrahim-Salman19/OCR#documentation",
                "headline": "B.L.A.S.T. OCR Engine: Technical Architecture and Performance Benchmarks",
                "description": "Complete architectural overview, reproducible benchmark harness, and integration guide for B.L.A.S.T. OCR.",
                "keywords": "Python OCR, ONNX OCR, Document Intelligence, Table Extraction, PDF to Markdown, Model Context Protocol, LangChain OCR Loader",
                "inLanguage": "en-US",
                "author": {"@id": "https://ibrahimsalman.vercel.app/#person"},
                "publisher": {
                    "@type": "Organization",
                    "name": "B.L.A.S.T. OCR Project",
                    "url": "https://github.com/Ibrahim-Salman19/OCR",
                },
            },
            {
                "@type": "Person",
                "@id": "https://ibrahimsalman.vercel.app/#person",
                "name": "Ibrahim Salman",
                "alternateName": "Ibrahim-Salman19",
                "url": "https://ibrahimsalman.vercel.app",
                "jobTitle": "Software Engineer",
                "sameAs": [
                    "https://github.com/Ibrahim-Salman19",
                    "https://www.linkedin.com/in/ibrahim-salman-dev/",
                    "https://www.upwork.com/freelancers/~013e1c54e9a3f7a2b8",
                ],
            },
            {
                "@type": "FAQPage",
                "@id": "https://github.com/Ibrahim-Salman19/OCR#faq",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": "Why is B.L.A.S.T. OCR faster than EasyOCR?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": "B.L.A.S.T.'s default engine (RapidOCR, ONNX Runtime with CUDA -> DirectML -> CPU fallback) replaced an EasyOCR/PyTorch baseline after a documented bake-off on the project's 14-page gold corpus, cutting average CPU per-page latency from ~117.8s to ~15.3s (a 7.7x improvement) while reducing mean CER by 18%. See ADR 0005 in the repository for the full methodology and raw results.",
                        },
                    },
                    {
                        "@type": "Question",
                        "name": "How does B.L.A.S.T. prevent memory leaks on large PDF archives?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": "B.L.A.S.T. implements a bounded sliding-window streaming architecture (StreamingPDFProcessor) that caps concurrent in-memory page buffers and recycles intermediate image tensors. A 1,000-page streaming stress test measured a growth slope of 0.0002 MB/page against a 0.005 MB/page fail threshold.",
                        },
                    },
                    {
                        "@type": "Question",
                        "name": "How does B.L.A.S.T. extract tables?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": "B.L.A.S.T. uses a morphological table detection and cell reconstruction engine (TableExtractor) that analyzes horizontal and vertical grid lines, merges spanning cells, and preserves hierarchical header structures into clean Markdown and HTML tables, scored against a built-in Tree-Edit-Distance (TEDS) evaluator for regression testing.",
                        },
                    },
                    {
                        "@type": "Question",
                        "name": "How do I connect B.L.A.S.T. OCR to Claude Desktop, Cursor, or Antigravity?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": "B.L.A.S.T. includes a native Model Context Protocol (MCP) server. Run 'python -m blast_ocr.mcp_server' or configure mcp.json to expose blast_ocr_process, blast_ocr_extract_tables, blast_ocr_extract_formulas, and blast_ocr_semantic_chunk tools with zero configuration.",
                        },
                    },
                    {
                        "@type": "Question",
                        "name": "How does B.L.A.S.T. generate dual-layer sandwich PDFs?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": "B.L.A.S.T. utilizes PyMuPDF to synthesize dual-layer searchable PDFs where the original scanned image is preserved on the visual layer while an invisible, selectable text layer is placed beneath it with exact word-level coordinate bounding box alignment.",
                        },
                    },
                ],
            },
            {
                "@type": "HowTo",
                "@id": "https://github.com/Ibrahim-Salman19/OCR#howto",
                "name": "How to Process Multi-Page PDFs to Markdown with B.L.A.S.T. OCR",
                "description": "Step-by-step guide to installing and processing PDF documents to Markdown with high accuracy.",
                "step": [
                    {
                        "@type": "HowToStep",
                        "name": "Install B.L.A.S.T. OCR",
                        "text": "Install core dependencies using pip install -r requirements.txt",
                    },
                    {
                        "@type": "HowToStep",
                        "name": "Initialize Pipeline",
                        "text": "Instantiate OCRPipeline(engine='rapidocr', secure_mode=True)",
                    },
                    {
                        "@type": "HowToStep",
                        "name": "Execute Document Processing",
                        "text": "Call pipeline.process(source_path='doc.pdf', formats=['markdown', 'pdf'])",
                    },
                ],
            },
            {
                "@type": "Dataset",
                "@id": "https://github.com/Ibrahim-Salman19/OCR#benchmark-dataset",
                "name": "B.L.A.S.T. OCR Gold Standard Evaluation Corpus",
                "description": "14-page multi-layout evaluation corpus with ground truth text, table geometries, reading order permutations, and character error rate (CER) baselines.",
                "license": "https://opensource.org/licenses/MIT",
                "measurementTechnique": "Character Error Rate (CER), Word Error Rate (WER), Kendall's Tau Reading Order, Tree-Edit-Distance (TEDS)",
            },
        ],
    }

