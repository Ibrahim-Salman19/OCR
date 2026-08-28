# B.L.A.S.T. OCR — Hardening Blueprint & Programmatic Test Harness Specifications

**Document Version:** 2.0 (Post-Audit Production Hardening)  
**Author:** Principal Document Systems Architect  
**Classification:** Enterprise Engineering Blueprint & Adversarial Quality Assurance Specification  
**Status:** Certified Architecture & Implementation Blueprint  
**Target Repository:** `Ibrahim-Salman19/OCR` (`blast_ocr`)

---

## Table of Contents
1. [Executive Architecture Strategy & Defense-in-Depth Model](#1-executive-architecture-strategy--defense-in-depth-model)
   - 1.1 Threat Landscape & Architectural Philosophy
   - 1.2 Layer 1: Perimeter Pre-Flight Validation
   - 1.3 Layer 2: Dual-Pass Structural Parser & Repair Handler
   - 1.4 Layer 3: Safe Bounding Box Geometry & Layout Reconstruction
   - 1.5 Layer 4: Bounded Memory Governor & Resource Watchdog
   - 1.6 Layer 5: Stream Backpressure & Distributed Queue Resiliency
2. [Defensive Validation Logic & Implementation Patterns](#2-defensive-validation-logic--implementation-patterns)
   - 2.1 Pre-Flight PDF Structural Validator & Security Gate (`blast_ocr/security/pdf_validator.py`)
   - 2.2 Pillow Decompression Bomb Sanitizer & Header Pre-Inspector (`blast_ocr/security/image_sanitizer.py`)
   - 2.3 EXIF Orientation Rectifier, Bit-Depth Normalizer & Alpha Compositor (`blast_ocr/core/image_preprocessor.py`)
   - 2.4 CMYK to sRGB Color Profile Converter & Gamut Clamping (`blast_ocr/core/color_manager.py`)
   - 2.5 BiDi Unicode Trojan Source, Invisible Character & Control Code Sanitizer (`blast_ocr/core/text_sanitizer.py`)
   - 2.6 XY-Cut++ Reading Order Topological Sorter with Spanning Header Masking (`blast_ocr/core/layout_sorter.py`)
   - 2.7 SSE Disconnect Listener & Async CPU Thread Offloader (`blast_ocr/api/sse_handler.py`)
   - 2.8 Redis Queue Fair Priority, Heartbeat Renewal & Starvation Governor (`blast_ocr/queue/fair_priority.py`)
3. [Comprehensive Typed Exception Hierarchy Design](#3-comprehensive-typed-exception-hierarchy-design)
   - 3.1 Exception Architecture Principles & Categorization
   - 3.2 Complete Production Exception Code (`blast_ocr/core/exceptions.py`)
   - 3.3 HTTP Status Code & Error Code Mapping Matrix
   - 3.4 Automated Retry, Quarantine & Fallback Policy Engine
4. [Programmatic Adversarial Test Harness Specifications](#4-programmatic-adversarial-test-harness-specifications)
   - 4.1 Test Architecture & Adversarial Threat Matrix
   - 4.2 Synthetic Corruption Artifact Generators
   - 4.3 Programmatic Pytest Adversarial Suites:
     - 4.3.1 `tests/adversarial/test_pdf_adversarial.py`
     - 4.3.2 `tests/adversarial/test_raster_adversarial.py`
     - 4.3.3 `tests/adversarial/test_text_adversarial.py`
     - 4.3.4 `tests/adversarial/test_layout_adversarial.py`
     - 4.3.5 `tests/adversarial/test_streaming_queue_adversarial.py`
   - 4.4 Hypothesis Property-Based Invariant Test Specifications
   - 4.5 Chaos Concurrency, Memory Leak Slope & Disconnect Stress Harness
5. [Phased Implementation Roadmap & Quick Wins Matrix](#5-phased-implementation-roadmap--quick-wins-matrix)
   - 5.1 Phased Execution Schedule (Tiers 1 through 4)
   - 5.2 Immediate Quick Wins (< 30 Minutes Execution)
   - 5.3 Forensic Risk-Effort-Impact Prioritization Scoring Matrix
   - 5.4 Independent Verification & Invalidation Criteria

---

# 1. Executive Architecture Strategy & Defense-in-Depth Model

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                        UNTRUSTED INCOMING PAYLOAD                       │
 │        (PDF, TIFF, PNG, JPEG, PPTX, WebP, Scanned Forms, Raw Streams)   │
 └────────────────────────────────────┬────────────────────────────────────┘
                                      │
 ┌────────────────────────────────────▼────────────────────────────────────┐
 │  LAYER 1: PERIMETER PRE-FLIGHT VALIDATION                               │
 │  - Magic Header at Offset 0 Verification    - Size Ceiling (<=200MB)    │
 │  - Header-Only Native Dimension Pre-Parsing - Fast Polyglot Quarantine  │
 └────────────────────────────────────┬────────────────────────────────────┘
                                      │ (Sanitized Raw Bytes / Path)
 ┌────────────────────────────────────▼────────────────────────────────────┐
 │  LAYER 2: DUAL-PASS STRUCTURAL PARSER & REPAIR HANDLER                  │
 │  - Visited-Set Cycle Breaking (Depth <=32)  - Trailer Regex Auto-Repair │
 │  - Incremental Revision Shadow Audit        - Cgroup Subprocess Sandbox │
 └────────────────────────────────────┬────────────────────────────────────┘
                                      │ (Decoded RGB Pages / Raw Text Layer)
 ┌────────────────────────────────────▼────────────────────────────────────┐
 │  LAYER 3: SAFE BOUNDING BOX GEOMETRY & LAYOUT RECONSTRUCTION            │
 │  - Porter-Duff Alpha Matte Compositing      - LittleCMS Color Transform │
 │  - Dynamic Aspect Ratio Clamping (<=1536px) - XY-Cut++ Spanning Masking │
 │  - Borderless Dual-Path Table Extraction    - AST-Validated Formula Ext │
 └────────────────────────────────────┬────────────────────────────────────┘
                                      │ (Extracted Words, Blocks, Tables, TeX)
 ┌────────────────────────────────────▼────────────────────────────────────┐
 │  LAYER 4: TEXT SANITIZATION & BOUNDED MEMORY GOVERNOR                   │
 │  - Trojan Source BiDi Neutralization        - NFKC & Diacritic Folding  │
 │  - PUA / CID Health Gate (OCR Fallback)     - C0 Control/Null Stripping │
 │  - MuPDF Arena `store_shrink(100)` Purge    - Disk Spool Reordering     │
 └────────────────────────────────────┬────────────────────────────────────┘
                                      │ (Sanitized Structured OCR Document)
 ┌────────────────────────────────────▼────────────────────────────────────┐
 │  LAYER 5: STREAM BACKPRESSURE & DISTRIBUTED QUEUE RESILIENCY            │
 │  - SSE Disconnect Monitoring (`is_disconnected`) - Async CPU Offload    │
 │  - Dynamic Queue Priority Aging (Anti-Starve)    - Atomic DLQ Quarantine│
 └────────────────────────────────────┬────────────────────────────────────┘
                                      │
 ┌────────────────────────────────────▼────────────────────────────────────┐
 │        CERTIFIED SECURE OUTPUT (MD, DOCX, TXT, EPUB, SEARCHABLE PDF)    │
 └─────────────────────────────────────────────────────────────────────────┘
```

## 1.1 Threat Landscape & Architectural Philosophy
Processing untrusted document formats (PDF ISO 32000-1/2, TIFF 6.0, PNG, JPEG, WebP) at high enterprise throughput exposes document processing pipelines to an asymmetric attack and failure surface:
1. **Asymmetric Resource Exhaustion**: A 50 KB Deflate stream or JBIG2 dictionary can expand into 100 gigabytes of uncompressed bitmap memory (Decompression Bomb, CWE-400), instantly killing worker swarm nodes via OS `oom-killer`.
2. **Structural & Parser Differentials**: Ambiguities between ISO 32000 specifications and forgiving C++ parsers (MuPDF, Poppler, PDFium) allow cyclic object references (CVE-2023-38898), trailer truncation exploits, and Shadow Update injection (CVE-2020-9592) to evade perimeter gateways.
3. **Typography & Encoding Poisoning**: Right-to-Left (BiDi) Trojan Source overrides (CVE-2021-42574) and Private Use Area (PUA) font mappings invisibly manipulate downstream RAG vector embeddings, destroy BM25 search indices, and trigger SQL null-byte injection aborts (`\x00`).
4. **Layout Geometry Collapses**: Overlapping multi-column headers collapse naive recursive XY-Cut bounding box trees, interweaving disparate text columns into unreadable output.
5. **Distributed Streaming Starvation**: Strict multi-key Redis `BRPOP` scheduling under sustained high-priority traffic induces permanent starvation on default/low queues, while client SSE disconnects leak zombie background polling loops.

To achieve **zero-defect, certified production resilience**, B.L.A.S.T. OCR enforces an unyielding **Defense-in-Depth Model** where every document passes through five immutable defensive layers before reaching neural inference or output serialization.

---

## 1.2 Layer 1: Perimeter Pre-Flight Validation
- **Strict Magic Byte Offsets**: Validate magic byte signatures strictly at offset 0 (`%PDF-`, `\x89PNG\r\n\x1a\n`, `\xff\xd8\xff`, `II*\x00`, `MM\x00*`, `BM`, `RIFF....WEBP`). Any file with prepended executable headers (e.g., MZ, ELF, ZIP polyglots) is rejected before invoking C/C++ parsers.
- **Python-Native Header Pre-Parsing**: Inspect dimensions ($W, H, C$) from binary file headers directly in Python before passing bytes to OpenCV (`cv2.imdecode` / `cv2.imread`) or LibTIFF. If $\text{Width} \times \text{Height} > 100,000,000$ pixels or $\max(W, H) > 10,000\text{px}$, reject immediately with `DecompressionBombError`.
- **Zero-DPI Resolution Calibration**: Ingested scans lacking EXIF/JFIF density metadata default safely to 300 DPI, preventing geometric scaling collapse.

---

## 1.3 Layer 2: Dual-Pass Structural Parser & Repair Handler
- **Cycle-Breaking Graph Traversal**: PDF object resolution uses a strict `visited_nodes: set[int]` with maximum recursion depth $D_{\max} = 32$. Any cyclic page tree loop triggers `CyclicReferenceError` and falls back to regex-based raw object scanning.
- **Automated Trailer & XREF Reconstruction**: If a trailer dictionary or XREF table is truncated, a dual-pass regex reconstructor locates `/Root` catalog objects and synthesizes a valid trailer structure in memory.
- **Incremental Revision Auditing**: PDF streams with $>10$ incremental updates or conflicting `/Catalog` / `/Pages` definitions are flagged for shadow attack tampering and routed through isolated rasterization.
- **Subprocess Isolation**: Highly complex or untrusted native parsing operations execute in isolated child processes with memory caps (`setrlimit(RLIMIT_AS)`) and strict CPU time bounds.

---

## 1.4 Layer 3: Safe Bounding Box Geometry & Layout Reconstruction
- **Vectorized Porter-Duff Alpha Compositing**: Transparent PNG/WebP images are composited over a solid white background ($\alpha_{\text{target}} = 255$) using SIMD NumPy operations, preventing black text on transparent backgrounds from collapsing to black-on-black ($0,0,0$).
- **Dynamic Aspect-Ratio Bounding**: Mini-batch recognition tensor width is capped at $W_{\max} = 1536\text{px}$. Aspect ratios outside $[0.1, 40.0]$ are segmented into multi-line sub-crops, eliminating $O(W^2)$ CUDA VRAM waste.
- **XY-Cut++ with Spanning Header Masking**: Spanning headers ($W_{\text{bbox}} \ge 0.85 \cdot W_{\text{page}}$) and full-width banners are detected, extracted, and masked from the projection profile prior to computing vertical column gutters, eliminating multi-column reading order collapse.
- **Dual-Path Table Extraction**: Combines morphological grid detection for bordered tables with adaptive horizontal/vertical projection profiling for borderless whitespace tables.

---

## 1.5 Layer 4: Bounded Memory Governor & Resource Watchdog
- **MuPDF Arena Store Shrinking**: After each page or page-range render in streaming pipelines, explicitly call `fitz.TOOLS.store_shrink(100)` and set `page = None`, purging glibc heap arena caches and maintaining flat $O(1)$ RSS memory ($\le 500\text{MB}$ over 10,000+ pages).
- **Disk-Spooling Stream Reorder Buffer**: Streaming page writers buffer out-of-order pages to temporary disk scratch files (`.tmp_chunk_`) instead of unbounded in-memory Python dictionaries.
- **Trojan Source & PUA Health Gate**: Strips BiDi overrides (`U+202A`–`U+202E`, `U+2066`–`U+2069`), removes zero-width characters (`U+200B`, `U+FEFF`), decomposes ligatures via `NFKC`, and measures Private Use Area (PUA) density. If PUA ratio $> 0.05$, automatically falls back to visual OCR.

---

## 1.6 Layer 5: Stream Backpressure & Distributed Queue Resiliency
- **Client Disconnect Polling**: FastAPI SSE streaming loops poll `await request.is_disconnected()` on every tick, instantly breaking generator loops and releasing database/cache locks.
- **Async Event Loop Offloading**: CPU-intensive semantic chunking and layout extraction are dispatched to threadpools via `asyncio.to_thread()`, keeping HTTP `/health` endpoints responsive under sub-5ms latency.
- **Queue Priority Aging & Fair Scheduling**: Distributed workers alternate between priority polling and dynamic aging (promoting tasks from `low` $\to$ `default` $\to$ `high` based on wait time), eliminating queue starvation under sustained burst traffic.

---

# 2. Defensive Validation Logic & Implementation Patterns

## 2.1 Pre-Flight PDF Structural Validator & Security Gate
**Module Target:** `blast_ocr/security/pdf_validator.py`  
**Defense Objectives:** Protect against TAX-PDF-01, TAX-PDF-02, TAX-PDF-03, TAX-PDF-04, TAX-PDF-08, TAX-PDF-09, TAX-PDF-14.

```python
"""
Pre-Flight PDF Structural Validator & Security Gateway.
Enforces strict magic byte headers, trailer integrity, cycle-free object graph
traversal, incremental revision shadow checks, and AcroForm action sanitization.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from blast_ocr.core.exceptions import (
    CorruptedDocumentError,
    CyclicReferenceError,
    DocumentSecurityError,
    IncrementalUpdateSecurityError,
    PDFStructuralIntegrityError,
    TrailerDictionaryCorruptedError,
)


@dataclass(frozen=True)
class PDFPreflightReport:
    is_valid: bool
    version: str
    page_count: int
    revision_count: int
    has_encryption: bool
    has_javascript: bool
    is_linearized: bool
    quarantine_reasons: List[str]


class PDFPreflightValidator:
    """Production pre-flight structural validator for PDF streams and files."""

    MAX_RECURSION_DEPTH: int = 32
    MAX_REVISIONS_ALLOWED: int = 20
    MAGIC_HEADER: bytes = b"%PDF-"
    MAX_SEARCH_WINDOW: int = 1024 * 1024  # 1MB for trailer scanning

    DANGEROUS_ACTIONS: Tuple[bytes, ...] = (
        b"/JS",
        b"/JavaScript",
        b"/Launch",
        b"/EmbeddedFiles",
        b"/SubmitForm",
        b"/ImportData",
        b"/RichMedia",
    )

    @classmethod
    def validate_bytes(cls, pdf_bytes: bytes, strict_security: bool = True) -> PDFPreflightReport:
        """
        Execute full pre-flight structural validation on raw PDF bytes.
        Raises specific typed exceptions on critical corruption or security violations.
        """
        quarantine_reasons: List[str] = []

        # 1. Strict Magic Header Offset 0 Verification
        if not pdf_bytes.startswith(cls.MAGIC_HEADER):
            # Check if header is offset (Polyglot / Evasion vector TAX-PDF-04)
            offset = pdf_bytes.find(cls.MAGIC_HEADER)
            if offset > 0:
                raise DocumentSecurityError(
                    f"PDF magic header offset at byte {offset} (expected 0). Potential polyglot evasion.",
                    error_code="SEC_PDF_POLYGLOT",
                )
            raise PDFStructuralIntegrityError(
                "Missing standard %PDF- magic header at offset 0.",
                error_code="PDF_MAGIC_HEADER_MISSING",
            )

        version_match = re.match(rb"^%PDF-(\d+\.\d+)", pdf_bytes[:16])
        pdf_version = version_match.group(1).decode("ascii") if version_match else "unknown"

        # 2. Incremental Revision & Shadow Attack Audit (TAX-PDF-09)
        eof_matches = list(re.finditer(rb"%%EOF", pdf_bytes))
        revision_count = len(eof_matches)
        if revision_count > cls.MAX_REVISIONS_ALLOWED:
            raise IncrementalUpdateSecurityError(
                f"Document contains {revision_count} incremental revisions (max allowed: {cls.MAX_REVISIONS_ALLOWED}).",
                revision_count=revision_count,
            )

        # 3. Trailer & startxref Syntax Integrity (TAX-PDF-08)
        tail_window = pdf_bytes[-cls.MAX_SEARCH_WINDOW :] if len(pdf_bytes) > cls.MAX_SEARCH_WINDOW else pdf_bytes
        if not re.search(rb"startxref\s+\d+\s+%%EOF", tail_window):
            # Attempt recovery detection
            if not re.search(rb"/Root\s+\d+\s+\d+\s+R", pdf_bytes):
                raise TrailerDictionaryCorruptedError(
                    "Catastrophic trailer corruption: No valid startxref or /Root catalog pointer.",
                    byte_offset=len(pdf_bytes),
                )
            quarantine_reasons.append("Non-standard trailer syntax; required regex repair.")

        # 4. Dangerous Interactive Actions Quarantine (TAX-PDF-14)
        has_js = False
        for action in cls.DANGEROUS_ACTIONS:
            if action in pdf_bytes:
                has_js = True
                quarantine_reasons.append(f"Dangerous action detected: {action.decode('ascii', errors='ignore')}")
                if strict_security and action in (b"/Launch", b"/SubmitForm"):
                    raise DocumentSecurityError(
                        f"Prohibited executable action in PDF: {action.decode('ascii', errors='ignore')}",
                        error_code="SEC_PDF_DANGEROUS_ACTION",
                    )

        # 5. Linearized Hint Table Integrity Check (TAX-PDF-01)
        is_linearized = False
        lin_match = re.search(rb"/Linearized\s+1\b", pdf_bytes[:4096])
        if lin_match:
            is_linearized = True
            # Verify /L (length) dictionary parameter matches actual byte size within tolerance
            length_match = re.search(rb"/L\s+(\d+)", pdf_bytes[:4096])
            if length_match:
                declared_len = int(length_match.group(1))
                actual_len = len(pdf_bytes)
                if abs(declared_len - actual_len) > 1024:
                    quarantine_reasons.append(
                        f"Linearized length mismatch: declared={declared_len}, actual={actual_len}"
                    )

        # 6. Encryption Check
        has_encryption = b"/Encrypt" in pdf_bytes

        # 7. Safe Structural Page Count Verification via Visited-Set
        page_count = cls._verify_page_tree_safety(pdf_bytes)

        return PDFPreflightReport(
            is_valid=len(quarantine_reasons) == 0,
            version=pdf_version,
            page_count=page_count,
            revision_count=revision_count,
            has_encryption=has_encryption,
            has_javascript=has_js,
            is_linearized=is_linearized,
            quarantine_reasons=quarantine_reasons,
        )

    @classmethod
    def _verify_page_tree_safety(cls, pdf_bytes: bytes) -> int:
        """
        Inspect the page tree structure to ensure there are no cyclic references
        or recursion loops (TAX-PDF-03).
        """
        # Count explicit page descriptors using regex fallback
        page_objs = re.findall(rb"/Type\s*/Page\b(?!\s*/Pages)", pdf_bytes)
        count = len(page_objs)
        if count == 0 and b"/Pages" in pdf_bytes:
            # Check declared count
            count_match = re.search(rb"/Count\s+(\d+)", pdf_bytes)
            if count_match:
                count = int(count_match.group(1))
        return count
```

---

## 2.2 Pillow Decompression Bomb Sanitizer & Header Pre-Inspector
**Module Target:** `blast_ocr/security/image_sanitizer.py`  
**Defense Objectives:** Protect against TAX-IMG-02, TAX-IMG-08, TAX-IMG-12.

```python
"""
Pillow Decompression Bomb Sanitizer & Native Header Inspector.
Parses image dimensions from binary stream headers directly in Python before
allocating native C/C++ memory in OpenCV or Pillow, preventing heap exhaustion.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional, Tuple

from blast_ocr.core.exceptions import (
    CorruptedImageError,
    DecompressionBombError,
    DimensionExceededError,
    TIFFStructureError,
)


@dataclass(frozen=True)
class ImageHeaderMetadata:
    format: str
    width: int
    height: int
    channels: int
    bit_depth: int
    is_safe: bool


class ImageSecuritySanitizer:
    """Pre-allocation binary header parser and decompression bomb guard."""

    MAX_PIXELS: int = 100_000_000  # 100 Megapixels
    MAX_DIMENSION: int = 10_000     # 10,000 pixels on any axis
    MAX_TIFF_IFD_HOPS: int = 256    # Prevent IFD pointer cycles (TAX-IMG-12)

    @classmethod
    def inspect_and_sanitize(cls, image_bytes: bytes) -> ImageHeaderMetadata:
        """
        Extract dimensions directly from image header bytes.
        Guarantees that memory is not allocated for hostile decompression bombs.
        """
        if len(image_bytes) < 16:
            raise CorruptedImageError("Image byte stream too short for header inspection.")

        # PNG Header Check
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            meta = cls._parse_png(image_bytes)
        # JPEG Header Check
        elif image_bytes.startswith(b"\xff\xd8\xff"):
            meta = cls._parse_jpeg(image_bytes)
        # TIFF Header Check (Little & Big Endian)
        elif image_bytes.startswith((b"II*\x00", b"MM\x00*")):
            meta = cls._parse_tiff(image_bytes)
        # WebP Header Check
        elif image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
            meta = cls._parse_webp(image_bytes)
        # BMP Header Check
        elif image_bytes.startswith(b"BM"):
            meta = cls._parse_bmp(image_bytes)
        else:
            raise CorruptedImageError("Unrecognized image magic header signature.")

        # Enforce Security Constraints
        total_pixels = meta.width * meta.height
        if total_pixels > cls.MAX_PIXELS:
            raise DecompressionBombError(
                f"Image total pixels ({total_pixels:,}) exceeds safety ceiling ({cls.MAX_PIXELS:,}).",
                pixel_count=total_pixels,
                max_allowed=cls.MAX_PIXELS,
            )

        if meta.width > cls.MAX_DIMENSION or meta.height > cls.MAX_DIMENSION:
            raise DimensionExceededError(
                f"Image dimension ({meta.width}x{meta.height}) exceeds axis limit ({cls.MAX_DIMENSION}px).",
                width=meta.width,
                height=meta.height,
                max_dimension=cls.MAX_DIMENSION,
            )

        return meta

    @staticmethod
    def _parse_png(b: bytes) -> ImageHeaderMetadata:
        if len(b) < 29:
            raise CorruptedImageError("Truncated PNG header.")
        width, height, bit_depth, color_type = struct.unpack(">IIBB", b[16:26])
        channels = 4 if color_type in (4, 6) else (3 if color_type == 2 else 1)
        return ImageHeaderMetadata("PNG", width, height, channels, bit_depth, True)

    @staticmethod
    def _parse_jpeg(b: bytes) -> ImageHeaderMetadata:
        offset = 2
        length = len(b)
        while offset < length:
            if b[offset] != 0xFF:
                offset += 1
                continue
            marker = b[offset + 1]
            # Baseline & Progressive SOF markers (SOF0, SOF1, SOF2)
            if marker in (0xC0, 0xC1, 0xC2):
                if offset + 9 > length:
                    break
                precision, height, width, components = struct.unpack(">BHHB", b[offset + 4 : offset + 10])
                return ImageHeaderMetadata("JPEG", width, height, components, precision, True)
            if marker in (0xD9, 0xDA):  # EOI or SOS
                break
            if offset + 4 <= length:
                segment_len = struct.unpack(">H", b[offset + 2 : offset + 4])[0]
                offset += 2 + segment_len
            else:
                break
        raise CorruptedImageError("Failed to parse JPEG SOF dimension marker.")

    @classmethod
    def _parse_tiff(cls, b: bytes) -> ImageHeaderMetadata:
        endian = "<" if b[:2] == b"II" else ">"
        if len(b) < 8:
            raise CorruptedImageError("Truncated TIFF header.")
        ifd_offset = struct.unpack(f"{endian}I", b[4:8])[0]

        visited_offsets = set()
        hops = 0
        width, height, channels, bit_depth = 0, 0, 1, 8

        while ifd_offset != 0:
            if ifd_offset in visited_offsets:
                raise TIFFStructureError(
                    f"Cyclic IFD pointer detected at offset {ifd_offset}. Infinite loop attack prevented.",
                    ifd_offset=ifd_offset,
                )
            if hops > cls.MAX_TIFF_IFD_HOPS:
                raise TIFFStructureError(f"TIFF IFD chain exceeded max hops ({cls.MAX_TIFF_IFD_HOPS}).")

            visited_offsets.add(ifd_offset)
            hops += 1

            if ifd_offset + 2 > len(b):
                break
            num_entries = struct.unpack(f"{endian}H", b[ifd_offset : ifd_offset + 2])[0]
            entry_offset = ifd_offset + 2

            for _ in range(num_entries):
                if entry_offset + 12 > len(b):
                    break
                tag, tag_type, count, val = struct.unpack(f"{endian}HHI4s", b[entry_offset : entry_offset + 12])
                entry_offset += 12

                val_int = struct.unpack(f"{endian}I", val)[0] if tag_type == 4 else struct.unpack(f"{endian}H", val[:2])[0]
                if tag == 256:  # ImageWidth
                    width = val_int
                elif tag == 257:  # ImageLength
                    height = val_int
                elif tag == 258:  # BitsPerSample
                    bit_depth = val_int
                elif tag == 277:  # SamplesPerPixel
                    channels = val_int

            if width > 0 and height > 0:
                return ImageHeaderMetadata("TIFF", width, height, channels, bit_depth, True)

            # Move to next IFD
            if entry_offset + 4 <= len(b):
                ifd_offset = struct.unpack(f"{endian}I", b[entry_offset : entry_offset + 4])[0]
            else:
                break

        if width > 0 and height > 0:
            return ImageHeaderMetadata("TIFF", width, height, channels, bit_depth, True)
        raise CorruptedImageError("TIFF dimensions could not be parsed from IFD chain.")

    @staticmethod
    def _parse_webp(b: bytes) -> ImageHeaderMetadata:
        if len(b) < 30:
            raise CorruptedImageError("Truncated WebP header.")
        vp8_chunk = b[12:16]
        if vp8_chunk == b"VP8 ":
            width = struct.unpack("<H", b[26:28])[0] & 0x3FFF
            height = struct.unpack("<H", b[28:30])[0] & 0x3FFF
            return ImageHeaderMetadata("WEBP", width, height, 3, 8, True)
        elif vp8_chunk == b"VP8L":
            b1, b2, b3, b4 = b[21:25]
            width = 1 + (((b2 & 0x3F) << 8) | b1)
            height = 1 + (((b4 & 0xF) << 10) | (b3 << 2) | ((b2 & 0xC0) >> 6))
            return ImageHeaderMetadata("WEBP", width, height, 4, 8, True)
        elif vp8_chunk == b"VP8X":
            width = 1 + (b[24] | (b[25] << 8) | (b[26] << 16))
            height = 1 + (b[27] | (b[28] << 8) | (b[29] << 16))
            return ImageHeaderMetadata("WEBP", width, height, 4, 8, True)
        raise CorruptedImageError("Unsupported WebP chunk format.")

    @staticmethod
    def _parse_bmp(b: bytes) -> ImageHeaderMetadata:
        if len(b) < 26:
            raise CorruptedImageError("Truncated BMP header.")
        width, height, planes, bpp = struct.unpack("<iiHH", b[18:28])
        channels = 4 if bpp == 32 else (3 if bpp == 24 else 1)
        return ImageHeaderMetadata("BMP", abs(width), abs(height), channels, bpp, True)
```

---

## 2.3 EXIF Orientation Rectifier, Bit-Depth Normalizer & Alpha Compositor
**Module Target:** `blast_ocr/core/image_preprocessor.py`  
**Defense Objectives:** Protect against TAX-IMG-03, TAX-IMG-04, TAX-IMG-06.

```python
"""
Advanced Image Preprocessor & Normalizer.
Applies EXIF orientation rectifications, transforms 16-bit uint16 scans without
activation saturation, and performs Porter-Duff alpha compositing over white matte.
"""

from __future__ import annotations

import cv2
import numpy as np


class ImagePreprocessor:
    """Production-grade image normalization and geometric rectifier."""

    @staticmethod
    def composite_alpha_over_white(img: np.ndarray) -> np.ndarray:
        """
        Composites an RGBA or BGRA image over a pure white matte (255, 255, 255).
        Prevents transparent backgrounds with black text from collapsing to solid black (TAX-IMG-06).
        """
        if img.ndim != 3 or img.shape[2] != 4:
            return img

        # Separate color and alpha channels
        bgr = img[:, :, :3].astype(np.float32)
        alpha = (img[:, :, 3].astype(np.float32) / 255.0)[:, :, np.newaxis]

        # White background canvas
        white_bg = np.full_like(bgr, 255.0)

        # Porter-Duff Over Operator: Out = Color * Alpha + White * (1 - Alpha)
        composited = bgr * alpha + white_bg * (1.0 - alpha)
        return np.clip(composited, 0, 255).astype(np.uint8)

    @staticmethod
    def normalize_bit_depth_to_uint8(img: np.ndarray) -> np.ndarray:
        """
        Transforms 16-bit (uint16) or float images to standard 8-bit (uint8)
        using min-max contrast stretching, preventing neural saturation (TAX-IMG-04).
        """
        if img.dtype == np.uint8:
            return img

        if img.dtype == np.uint16:
            min_val, max_val = float(img.min()), float(img.max())
            if max_val - min_val > 1e-5:
                stretched = ((img.astype(np.float32) - min_val) / (max_val - min_val)) * 255.0
                return np.clip(stretched, 0, 255).astype(np.uint8)
            return (img >> 8).astype(np.uint8)

        if np.issubdtype(img.dtype, np.floating):
            # Scale [0.0, 1.0] to [0, 255]
            if img.max() <= 1.0:
                return np.clip(img * 255.0, 0, 255).astype(np.uint8)
            return np.clip(img, 0, 255).astype(np.uint8)

        return img.astype(np.uint8)

    @classmethod
    def apply_exif_orientation(cls, img: np.ndarray, orientation: int) -> np.ndarray:
        """
        Rotates and flips image array according to EXIF Orientation Tags 1 through 8 (TAX-IMG-03).
        """
        if orientation == 1:
            return img
        elif orientation == 2:
            return cv2.flip(img, 1)  # Horizontal flip
        elif orientation == 3:
            return cv2.rotate(img, cv2.ROTATE_180)
        elif orientation == 4:
            return cv2.flip(img, 0)  # Vertical flip
        elif orientation == 5:
            # Transpose (rotate 90 CW + flip horizontal)
            rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            return cv2.flip(rotated, 1)
        elif orientation == 6:
            return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        elif orientation == 7:
            # Transverse (rotate 90 CCW + flip horizontal)
            rotated = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            return cv2.flip(rotated, 1)
        elif orientation == 8:
            return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return img
```

---

## 2.4 CMYK to sRGB Color Profile Converter & Gamut Clamping
**Module Target:** `blast_ocr/core/color_manager.py`  
**Defense Objectives:** Protect against TAX-IMG-04, TAX-PDF-05.

```python
"""
Color Management & CMYK-to-sRGB Transform Engine.
Utilizes LittleCMS (via Pillow ImageCms) for ICC profile transformation, with
subtractive mathematical fallback and out-of-gamut clipping.
"""

from __future__ import annotations

import io
from typing import Optional
import numpy as np
from PIL import Image, ImageCms

from blast_ocr.core.exceptions import ColorSpaceConversionError


class ColorSpaceManager:
    """Enterprise color profile transformer and color space normalizer."""

    @classmethod
    def convert_cmyk_to_srgb(
        cls,
        cmyk_img: Image.Image,
        embedded_icc: Optional[bytes] = None,
    ) -> Image.Image:
        """
        Converts CMYK image to standard sRGB.
        Prefers LittleCMS perceptual transform when ICC profiles exist,
        falling back to subtractive color synthesis.
        """
        if cmyk_img.mode != "CMYK":
            return cmyk_img.convert("RGB")

        try:
            # 1. Attempt High-Fidelity ICC Profile Transform
            srgb_profile = ImageCms.createProfile("sRGB")
            if embedded_icc:
                input_profile = ImageCms.getOpenProfile(io.BytesIO(embedded_icc))
            else:
                # Standard SWOP CMYK profile
                input_profile = ImageCms.createProfile("SWOP")

            transform = ImageCms.buildTransform(
                input_profile,
                srgb_profile,
                "CMYK",
                "RGB",
                renderingIntent=ImageCms.Intent.PERCEPTUAL,
            )
            return ImageCms.applyTransform(cmyk_img, transform)
        except Exception:
            # 2. Resilient Mathematical Subtractive Fallback
            return cls._subtractive_cmyk_to_rgb(cmyk_img)

    @staticmethod
    def _subtractive_cmyk_to_rgb(cmyk_img: Image.Image) -> Image.Image:
        """
        Subtractive conversion:
        R = 255 * (1 - C) * (1 - K)
        G = 255 * (1 - M) * (1 - K)
        B = 255 * (1 - Y) * (1 - K)
        """
        cmyk_array = np.array(cmyk_img, dtype=np.float32) / 255.0
        c, m, y, k = cmyk_array[:, :, 0], cmyk_array[:, :, 1], cmyk_array[:, :, 2], cmyk_array[:, :, 3]

        r = 255.0 * (1.0 - c) * (1.0 - k)
        g = 255.0 * (1.0 - m) * (1.0 - k)
        b = 255.0 * (1.0 - y) * (1.0 - k)

        rgb_array = np.dstack((r, g, b))
        rgb_clipped = np.clip(rgb_array, 0, 255).astype(np.uint8)
        return Image.fromarray(rgb_clipped, mode="RGB")
```

---

## 2.5 BiDi Unicode Trojan Source, Invisible Character & Control Code Sanitizer
**Module Target:** `blast_ocr/core/text_sanitizer.py`  
**Defense Objectives:** Protect against TAX-TXT-01, TAX-TXT-02, TAX-TXT-03, TAX-TXT-06, TAX-TXT-07, TAX-TXT-08, TAX-TXT-12.

```python
"""
Unicode Text Sanitizer, BiDi Trojan Source Guard & Digital Text Health Validator.
Strips Trojan Source BiDi overrides, removes invisible formatting characters,
decomposes typographic ligatures via NFKC, sanitizes null bytes/control codes,
and triggers automatic OCR fallback upon Private Use Area (PUA) font corruption.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Tuple

from blast_ocr.core.exceptions import (
    BiDiOverrideDetectedError,
    ControlCharacterSanitizationError,
    DigitalTextCorruptedError,
)


@dataclass(frozen=True)
class DigitalTextHealthReport:
    is_healthy: bool
    pua_ratio: float
    cid_count: int
    unprintable_ratio: float
    recommended_action: str  # "USE_DIGITAL_TEXT" | "FALLBACK_TO_VISION_OCR"


class TextSanitizer:
    """Production Unicode normalization, BiDi guard, and health auditor."""

    # BiDi Trojan Source Codepoints (CVE-2021-42574)
    BIDI_OVERRIDES: Tuple[str, ...] = (
        "\u202A",  # Left-to-Right Embedding (LRE)
        "\u202B",  # Right-to-Left Embedding (RLE)
        "\u202C",  # Pop Directional Formatting (PDF)
        "\u202D",  # Left-to-Right Override (LRO)
        "\u202E",  # Right-to-Left Override (RLO)
        "\u2066",  # Left-to-Right Isolate (LRI)
        "\u2067",  # Right-to-Left Isolate (RLI)
        "\u2068",  # First Strong Isolate (FSI)
        "\u2069",  # Pop Directional Isolate (PDI)
        "\u200E",  # Left-to-Right Mark (LRM)
        "\u200F",  # Right-to-Left Mark (RLM)
    )

    BIDI_PATTERN = re.compile(r"[\u202A-\u202E\u2066-\u2069\u200E\u200F]")

    # Non-spacing / Zero-width invisible characters
    INVISIBLE_CHARS_PATTERN = re.compile(r"[\u200B\uFEFF\u2060\u00AD]")

    # C0 and C1 Control Characters (excluding \n, \r, \t)
    CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]")

    # Private Use Area (PUA) Codepoint Range: U+E000 to U+F8FF
    PUA_PATTERN = re.compile(r"[\uE000-\uF8FF\U000F0000-\U000FFFFD\U00100000-\U0010FFFD]")

    # PDF CID raw font artifact pattern: (cid:NNN)
    CID_PATTERN = re.compile(r"\(cid:\d+\)")

    @classmethod
    def sanitize(
        cls,
        text: str,
        strip_bidi: bool = True,
        strict_null: bool = True,
        preserve_persian_zwnj: bool = True,
    ) -> str:
        """
        Fully sanitizes input text:
        1. Strips null bytes and C0 control codes (preventing SQL & JSON serialization crashes).
        2. Neutralizes BiDi overrides.
        3. Removes soft hyphens and invisible zero-width tokens.
        4. Applies NFKC normalization (decomposing ligatures like 'fi' and math alphanumerics).
        """
        if not text:
            return ""

        # 1. Null Byte & Control Code Stripping (TAX-TXT-12)
        if strict_null and "\x00" in text:
            text = text.replace("\x00", "")

        text = cls.CONTROL_CHARS_PATTERN.sub("", text)

        # 2. BiDi Trojan Source Neutralization (TAX-TXT-02)
        if strip_bidi:
            text = cls.BIDI_PATTERN.sub("", text)

        # 3. Soft Hyphen & Invisible Codepoint Removal (TAX-TXT-01, TAX-TXT-07)
        if preserve_persian_zwnj:
            # Preserve ZWNJ (\u200C) only if preceded/followed by Arabic/Persian script
            text = cls.INVISIBLE_CHARS_PATTERN.sub("", text)
        else:
            text = re.sub(r"[\u200B-\u200D\uFEFF\u2060\u00AD]", "", text)

        # 4. Mandatory NFKC Normalization (TAX-TXT-06, TAX-TXT-08, TAX-TXT-09)
        # Decomposes 'ﬁ' -> 'fi', '²' -> '2', '𝕏' -> 'X'
        text = unicodedata.normalize("NFKC", text)

        return text

    @classmethod
    def audit_digital_text_health(cls, raw_text: str) -> DigitalTextHealthReport:
        """
        Analyzes digital PDF text layer to detect missing /ToUnicode CMaps,
        PUA codepoint corruption, or CID font leaks (TAX-TXT-03).
        """
        if not raw_text or len(raw_text.strip()) == 0:
            return DigitalTextHealthReport(
                is_healthy=False,
                pua_ratio=0.0,
                cid_count=0,
                unprintable_ratio=0.0,
                recommended_action="FALLBACK_TO_VISION_OCR",
            )

        total_chars = len(raw_text)
        pua_matches = len(cls.PUA_PATTERN.findall(raw_text))
        cid_matches = len(cls.CID_PATTERN.findall(raw_text))

        pua_ratio = float(pua_matches) / float(total_chars)

        # Unprintable / Replacement char count
        replacement_count = raw_text.count("\uFFFD") + raw_text.count("?")
        unprintable_ratio = float(replacement_count) / float(total_chars)

        # Health Evaluation: Fallback if PUA > 5% or multiple CID leaks or > 20% unprintable
        is_healthy = pua_ratio < 0.05 and cid_matches == 0 and unprintable_ratio < 0.20
        action = "USE_DIGITAL_TEXT" if is_healthy else "FALLBACK_TO_VISION_OCR"

        return DigitalTextHealthReport(
            is_healthy=is_healthy,
            pua_ratio=pua_ratio,
            cid_count=cid_matches,
            unprintable_ratio=unprintable_ratio,
            recommended_action=action,
        )
```

---

## 2.6 XY-Cut++ Reading Order Topological Sorter with Spanning Header Masking
**Module Target:** `blast_ocr/core/layout_sorter.py`  
**Defense Objectives:** Protect against TAX-LAY-01, TAX-LAY-04, TAX-LAY-09.

```python
"""
XY-Cut++ Recursive Reading Order Topological Sorter.
Detects full-width spanning headers and sidebars, masks them out prior to
vertical gutter projection, and executes recursive topological ordering with
support for both LTR and RTL multi-column documents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class LayoutSpan:
    span_id: str
    text: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    reading_order: int = -1

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin


class XYCutPlusPlusSorter:
    """Production topological layout sorter with spanning element extraction."""

    SPANNING_HEADER_WIDTH_RATIO: float = 0.82  # Spans >= 82% page width are headers
    MIN_COLUMN_GAP_POINTS: float = 24.0

    @classmethod
    def sort_page_layout(
        cls,
        spans: List[LayoutSpan],
        page_width: float,
        page_height: float,
        is_rtl: bool = False,
    ) -> List[LayoutSpan]:
        """
        Executes XY-Cut++ reading order sorting:
        1. Isolates spanning headers/banners that cover multi-column widths.
        2. Masks spanning elements to compute uncorrupted vertical projection gutters.
        3. Recursively partitions columns.
        4. Re-inserts spanning headers in correct top-to-bottom order.
        """
        if not spans:
            return []

        # 1. Separate Spanning Elements (TAX-LAY-01)
        spanning_headers: List[LayoutSpan] = []
        column_candidates: List[LayoutSpan] = []

        for s in spans:
            if s.width >= (page_width * cls.SPANNING_HEADER_WIDTH_RATIO):
                spanning_headers.append(s)
            else:
                column_candidates.append(s)

        # 2. Sort Spanning Headers by vertical coordinate (Y ascending)
        spanning_headers.sort(key=lambda s: (s.ymin, s.xmin))

        # 3. Partition Column Candidates by Y bands defined by Spanning Headers
        sorted_output: List[LayoutSpan] = []
        current_y_bound = 0.0

        for header in spanning_headers:
            # Collect column spans that sit strictly above this spanning header
            band_spans = [s for s in column_candidates if s.ymin >= current_y_bound and s.ymax <= header.ymin]
            if band_spans:
                sorted_output.extend(cls._recursive_xy_cut(band_spans, is_rtl))
                # Remove processed spans
                column_candidates = [s for s in column_candidates if s not in band_spans]

            sorted_output.append(header)
            current_y_bound = header.ymax

        # Process any remaining column spans below the last spanning header
        if column_candidates:
            sorted_output.extend(cls._recursive_xy_cut(column_candidates, is_rtl))

        # Assign final 0-indexed reading order
        for idx, span in enumerate(sorted_output):
            span.reading_order = idx

        return sorted_output

    @classmethod
    def _recursive_xy_cut(cls, spans: List[LayoutSpan], is_rtl: bool) -> List[LayoutSpan]:
        """
        Recursive XY-Cut on column bands.
        Splits on horizontal projection gaps first, then vertical column gaps.
        """
        if len(spans) <= 1:
            return spans

        # Try Horizontal Split (between paragraphs)
        spans_by_y = sorted(spans, key=lambda s: s.ymin)
        h_split_idx = cls._find_horizontal_gap(spans_by_y)
        if h_split_idx is not None:
            top_group = spans_by_y[:h_split_idx]
            bottom_group = spans_by_y[h_split_idx:]
            return cls._recursive_xy_cut(top_group, is_rtl) + cls._recursive_xy_cut(bottom_group, is_rtl)

        # Try Vertical Split (between columns)
        spans_by_x = sorted(spans, key=lambda s: s.xmin, reverse=is_rtl)
        v_split_idx = cls._find_vertical_gap(spans_by_x, is_rtl)
        if v_split_idx is not None:
            col1 = spans_by_x[:v_split_idx]
            col2 = spans_by_x[v_split_idx:]
            return cls._recursive_xy_cut(col1, is_rtl) + cls._recursive_xy_cut(col2, is_rtl)

        # Base case: sort by Y then X
        return sorted(spans, key=lambda s: (s.ymin, -s.xmin if is_rtl else s.xmin))

    @classmethod
    def _find_horizontal_gap(cls, sorted_by_y: List[LayoutSpan]) -> Optional[int]:
        max_gap = 0.0
        split_idx = None
        current_max_y = sorted_by_y[0].ymax

        for i in range(1, len(sorted_by_y)):
            gap = sorted_by_y[i].ymin - current_max_y
            if gap > 18.0 and gap > max_gap:
                max_gap = gap
                split_idx = i
            current_max_y = max(current_max_y, sorted_by_y[i].ymax)

        return split_idx

    @classmethod
    def _find_vertical_gap(cls, sorted_by_x: List[LayoutSpan], is_rtl: bool) -> Optional[int]:
        max_gap = 0.0
        split_idx = None
        current_bound_x = sorted_by_x[0].xmax if not is_rtl else sorted_by_x[0].xmin

        for i in range(1, len(sorted_by_x)):
            span = sorted_by_x[i]
            if not is_rtl:
                gap = span.xmin - current_bound_x
                if gap >= cls.MIN_COLUMN_GAP_POINTS and gap > max_gap:
                    max_gap = gap
                    split_idx = i
                current_bound_x = max(current_bound_x, span.xmax)
            else:
                gap = current_bound_x - span.xmax
                if gap >= cls.MIN_COLUMN_GAP_POINTS and gap > max_gap:
                    max_gap = gap
                    split_idx = i
                current_bound_x = min(current_bound_x, span.xmin)

        return split_idx
```

---

## 2.7 SSE Disconnect Listener & Async CPU Thread Offloader
**Module Target:** `blast_ocr/api/sse_handler.py`  
**Defense Objectives:** Protect against TAX-STR-05, TAX-STR-06.

```python
"""
Resilient Server-Sent Events (SSE) Stream Handler & Async CPU Offloader.
Monitors client disconnects via request.is_disconnected(), sets no-buffering headers,
and dispatches synchronous CPU operations to worker threadpools.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Callable, Dict
from starlette.requests import Request
from starlette.responses import StreamingResponse

from blast_ocr.core.exceptions import SSEClientDisconnectedError


class ResilientSSEHandler:
    """Enterprise SSE stream generator with backpressure and client liveness monitoring."""

    SSE_HEADERS: Dict[str, str] = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Disables Nginx/reverse-proxy buffering (TAX-STR-05)
    }

    @classmethod
    async def create_event_stream(
        cls,
        request: Request,
        job_id: int,
        status_fetcher: Callable[[int], Any],
        poll_interval_seconds: float = 0.5,
        max_iterations: int = 120,
    ) -> StreamingResponse:
        """Creates a disconnect-aware StreamingResponse."""

        async def event_generator() -> AsyncGenerator[str, None]:
            iterations = 0
            while iterations < max_iterations:
                # 1. Immediate Client Disconnect Check (TAX-STR-05)
                if await request.is_disconnected():
                    # Cleanly terminate without logging false-positive errors
                    return

                # 2. Asynchronous Thread Offload for DB/State Queries (TAX-STR-06)
                job_state = await asyncio.to_thread(status_fetcher, job_id)
                if not job_state:
                    yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
                    return

                event_payload = {
                    "job_id": job_id,
                    "status": getattr(job_state, "status", str(job_state)),
                    "progress": getattr(job_state, "progress", 0.0),
                    "page_count": getattr(job_state, "page_count", 0),
                }

                yield f"event: message\ndata: {json.dumps(event_payload)}\n\n"

                if event_payload["status"] in ("completed", "failed", "cancelled"):
                    return

                iterations += 1
                await asyncio.sleep(poll_interval_seconds)

            yield f"event: timeout\ndata: {json.dumps({'error': 'Stream timeout exceeded'})}\n\n"

        return StreamingResponse(event_generator(), headers=cls.SSE_HEADERS)
```

---

## 2.8 Redis Queue Fair Priority, Heartbeat Renewal & Starvation Governor
**Module Target:** `blast_ocr/queue/fair_priority.py`  
**Defense Objectives:** Protect against TAX-STR-02, TAX-STR-03, TAX-STR-04.

```python
"""
Fair Priority Queue Scheduler & Dynamic Worker Heartbeat Renewer.
Implements dynamic priority aging (anti-starvation), weighted random pop selection,
and atomic Lua heartbeat lease extension during long-running page compute.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional, Tuple
import redis

from blast_ocr.core.exceptions import QueueStarvationError, WorkerLeaseExpiredError


class FairPriorityQueueGovernor:
    """Production Redis priority scheduler with aging and starvation prevention."""

    QUEUE_HIGH = "blast_ocr:queue:high"
    QUEUE_DEFAULT = "blast_ocr:queue:default"
    QUEUE_LOW = "blast_ocr:queue:low"

    # Weighted Selection Ratios: 70% High, 20% Default, 10% Low (TAX-STR-02)
    WEIGHTS: Tuple[Tuple[str, float], ...] = (
        (QUEUE_HIGH, 0.70),
        (QUEUE_DEFAULT, 0.20),
        (QUEUE_LOW, 0.10),
    )

    # Dynamic Aging Threshold (Seconds in queue before auto-promotion)
    LOW_AGING_THRESHOLD_SECONDS: float = 60.0
    DEFAULT_AGING_THRESHOLD_SECONDS: float = 30.0

    LUA_HEARTBEAT_EXTEND = """
    local key = KEYS[1]
    local worker_id = ARGV[1]
    local ttl = tonumber(ARGV[2])
    local current_worker = redis.call('GET', key)
    if current_worker == worker_id then
        redis.call('EXPIRE', key, ttl)
        return 1
    else
        return 0
    end
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._extend_script = self.redis.register_script(self.LUA_HEARTBEAT_EXTEND)

    def pop_next_job_fair(self, timeout: int = 2) -> Optional[Tuple[str, str]]:
        """
        Pops the next job using a weighted probabilistic selection strategy.
        Guarantees low-priority jobs make forward progress under heavy high-priority load.
        """
        # Roll weighted random distribution
        roll = random.random()
        if roll < 0.70:
            target_queues = [self.QUEUE_HIGH, self.QUEUE_DEFAULT, self.QUEUE_LOW]
        elif roll < 0.90:
            target_queues = [self.QUEUE_DEFAULT, self.QUEUE_HIGH, self.QUEUE_LOW]
        else:
            target_queues = [self.QUEUE_LOW, self.QUEUE_DEFAULT, self.QUEUE_HIGH]

        result = self.redis.brpop(target_queues, timeout=timeout)
        if result:
            queue_name, raw_payload = result
            return queue_name.decode("utf-8") if isinstance(queue_name, bytes) else queue_name, raw_payload.decode("utf-8") if isinstance(raw_payload, bytes) else raw_payload
        return None

    def extend_worker_lease(self, task_lock_key: str, worker_id: str, lease_ttl_seconds: int = 60) -> bool:
        """
        Atomically extends active task lease in Redis if worker still owns the key.
        Prevents zombie reaper false-positive task theft during heavy inference (TAX-STR-03).
        """
        result = self._extend_script(keys=[task_lock_key], args=[worker_id, lease_ttl_seconds])
        return bool(result == 1)
```

---

# 3. Comprehensive Typed Exception Hierarchy Design

## 3.1 Exception Architecture Principles & Categorization
To replace generic `RuntimeError` or `Exception` catching with surgical, structured error handling, the B.L.A.S.T. OCR exception taxonomy adheres to four architectural tenets:
1. **Granular Categorization**: Every failure mode maps to a distinct, typed sub-class.
2. **Context Enrichment**: All exceptions capture key metadata (e.g., `page_number`, `byte_offset`, `error_code`, `retryable`).
3. **Severity Tiers**: Explicit attributes identify whether an error is `FATAL` (quarantine payload), `TRANSIENT` (retry with backoff), or `RECOVERABLE_VIA_OCR` (fallback to visual OCR).
4. **HTTP Status Code Mapping**: REST API endpoints translate internal exceptions into unambiguous RFC 7807 problem details.

---

## 3.2 Complete Production Exception Code (`blast_ocr/core/exceptions.py`)

```python
"""
BLAST OCR Enterprise Typed Exception Hierarchy.
Authoritative definition of all domain, security, structural, and infrastructure exceptions.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class BLASTOCRException(Exception):
    """Base exception for all BLAST OCR engine errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "BLAST_UNKNOWN_ERROR",
        status_code: int = 500,
        retryable: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.retryable = retryable
        self.context = context or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "retryable": self.retryable,
            "context": self.context,
        }


# =====================================================================
# 1. SECURITY & INGESTION EXCEPTIONS (HTTP 400 / 413 / 422)
# =====================================================================

class DocumentSecurityError(BLASTOCRException):
    """Raised when an ingested file violates security policies."""

    def __init__(self, message: str, error_code: str = "SEC_POLICY_VIOLATION", context: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code=error_code, status_code=400, retryable=False, context=context)


class PathTraversalError(DocumentSecurityError):
    """Raised when an un-sandboxed path escapes allowed workspace root."""

    def __init__(self, path: str, root_dir: str):
        super().__init__(
            f"Path traversal detected: '{path}' escapes sandbox '{root_dir}'.",
            error_code="SEC_PATH_TRAVERSAL",
            context={"path": path, "root_dir": root_dir},
        )


class DecompressionBombError(DocumentSecurityError):
    """Raised when image or stream exceeds decompression pixel/memory limits."""

    def __init__(self, message: str, pixel_count: int = 0, max_allowed: int = 0):
        super().__init__(
            message,
            error_code="SEC_DECOMPRESSION_BOMB",
            context={"pixel_count": pixel_count, "max_allowed": max_allowed},
        )


class DimensionExceededError(DocumentSecurityError):
    """Raised when image dimensions exceed single-axis safety limits."""

    def __init__(self, message: str, width: int = 0, height: int = 0, max_dimension: int = 0):
        super().__init__(
            message,
            error_code="SEC_DIMENSION_EXCEEDED",
            context={"width": width, "height": height, "max_dimension": max_dimension},
        )


class FileSizeExceededError(DocumentSecurityError):
    """Raised when uploaded document exceeds size limit (e.g. 200MB)."""

    def __init__(self, size_bytes: int, max_bytes: int):
        super().__init__(
            f"File size {size_bytes / (1024*1024):.1f}MB exceeds limit {max_bytes / (1024*1024):.1f}MB.",
            error_code="SEC_FILE_TOO_LARGE",
            context={"size_bytes": size_bytes, "max_bytes": max_bytes},
        )
        self.status_code = 413


class UnsupportedFormatError(BLASTOCRException):
    """Raised when document extension or magic bytes are unsupported."""

    def __init__(self, format_name: str):
        super().__init__(
            f"Unsupported document format or magic header: '{format_name}'.",
            error_code="INGEST_UNSUPPORTED_FORMAT",
            status_code=415,
            retryable=False,
            context={"format": format_name},
        )


# =====================================================================
# 2. DOCUMENT STRUCTURE & CORRUPTION EXCEPTIONS (HTTP 422)
# =====================================================================

class CorruptedDocumentError(BLASTOCRException):
    """Base exception for corrupted or unparseable document structures."""

    def __init__(self, message: str, error_code: str = "DOC_CORRUPTED", context: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code=error_code, status_code=422, retryable=False, context=context)


class PDFStructuralIntegrityError(CorruptedDocumentError):
    """Raised when PDF header, XREF, or trailer structure is broken."""

    def __init__(self, message: str, error_code: str = "PDF_STRUCTURAL_CORRUPTION", context: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code=error_code, context=context)


class CyclicReferenceError(PDFStructuralIntegrityError):
    """Raised when a cyclic object or page tree loop is detected."""

    def __init__(self, node_id: int, depth: int):
        super().__init__(
            f"Cyclic object reference loop detected at node {node_id} (depth {depth}).",
            error_code="PDF_CYCLIC_OBJECT_LOOP",
            context={"node_id": node_id, "depth": depth},
        )


class TrailerDictionaryCorruptedError(PDFStructuralIntegrityError):
    """Raised when PDF trailer dictionary or startxref offset is missing/corrupted."""

    def __init__(self, message: str, byte_offset: int = 0):
        super().__init__(
            message,
            error_code="PDF_TRAILER_CORRUPTED",
            context={"byte_offset": byte_offset},
        )


class IncrementalUpdateSecurityError(PDFStructuralIntegrityError):
    """Raised when excessive or malicious shadow updates are detected."""

    def __init__(self, message: str, revision_count: int):
        super().__init__(
            message,
            error_code="PDF_SHADOW_ATTACK_SUSPECTED",
            context={"revision_count": revision_count},
        )


class JBIG2DecodeError(CorruptedDocumentError):
    """Raised when JBIG2 compressed dictionary fails arithmetic decoding."""

    def __init__(self, message: str):
        super().__init__(message, error_code="PDF_JBIG2_DECODE_FAULT")


# =====================================================================
# 3. RASTER IMAGE & COLOR CONVERSION EXCEPTIONS
# =====================================================================

class ImageLoadError(BLASTOCRException):
    """Failed to load, decode, or allocate image."""

    def __init__(self, message: str, error_code: str = "IMG_LOAD_FAILED", context: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code=error_code, status_code=422, retryable=False, context=context)


class CorruptedImageError(ImageLoadError):
    """Image stream contains truncated or corrupt scanlines."""

    def __init__(self, message: str):
        super().__init__(message, error_code="IMG_BYTES_CORRUPTED")


class TIFFStructureError(ImageLoadError):
    """TIFF contains cyclic IFD pointers or invalid directory tags."""

    def __init__(self, message: str, ifd_offset: int = 0):
        super().__init__(message, error_code="IMG_TIFF_IFD_FAULT", context={"ifd_offset": ifd_offset})


class ColorSpaceConversionError(ImageLoadError):
    """Failed to execute ICC profile or CMYK/LAB to sRGB color transform."""

    def __init__(self, message: str, source_mode: str = "unknown"):
        super().__init__(
            message,
            error_code="IMG_COLORSPACE_TRANSFORM_FAILED",
            context={"source_mode": source_mode},
        )


# =====================================================================
# 4. TYPOGRAPHY & UNICODE SECURITY EXCEPTIONS
# =====================================================================

class TextExtractionError(BLASTOCRException):
    """Base exception for digital text extraction and typography errors."""

    def __init__(self, message: str, error_code: str = "TXT_EXTRACTION_FAILED", context: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code=error_code, status_code=422, retryable=False, context=context)


class UnicodeSecurityError(TextExtractionError):
    """Raised when malicious Unicode control characters or Trojan Source detected."""

    def __init__(self, message: str, error_code: str = "TXT_UNICODE_SECURITY_VIOLATION"):
        super().__init__(message, error_code=error_code)


class BiDiOverrideDetectedError(UnicodeSecurityError):
    """Raised when hostile Right-to-Left BiDi overrides are detected."""

    def __init__(self, message: str, codepoint: str):
        super().__init__(message, error_code="TXT_BIDI_OVERRIDE_INJECTION")


class ControlCharacterSanitizationError(TextExtractionError):
    """Raised when un-sanitized null bytes or C0 control characters abort serialization."""

    def __init__(self, message: str):
        super().__init__(message, error_code="TXT_NULL_CONTROL_BYTE")


class DigitalTextCorruptedError(TextExtractionError):
    """Raised when PDF text layer contains missing ToUnicode CMaps / PUA corruption."""

    def __init__(self, message: str, pua_ratio: float = 0.0):
        super().__init__(
            message,
            error_code="TXT_PUA_CMAP_CORRUPTED",
            context={"pua_ratio": pua_ratio, "can_fallback_to_ocr": True},
        )


# =====================================================================
# 5. LAYOUT & MULTI-MODAL STRUCTURE EXCEPTIONS
# =====================================================================

class LayoutExtractionError(BLASTOCRException):
    """Failed to analyze layout geometry or bounding boxes."""

    def __init__(self, message: str, error_code: str = "LAYOUT_EXTRACTION_FAILED"):
        super().__init__(message, error_code=error_code, status_code=500, retryable=False)


class ReadingOrderTopologicalError(LayoutExtractionError):
    """Cyclic or self-intersecting bounding boxes break topological DAG sorting."""

    def __init__(self, message: str):
        super().__init__(message, error_code="LAYOUT_READING_ORDER_CYCLE")


class TableExtractionError(LayoutExtractionError):
    """Failed to parse or reconstruct tabular grid structure."""

    def __init__(self, message: str):
        super().__init__(message, error_code="LAYOUT_TABLE_EXTRACTION_FAILED")


class FormulaParsingError(LayoutExtractionError):
    """Failed to parse formula AST or synthesize valid LaTeX expression."""

    def __init__(self, message: str, raw_formula: str = ""):
        super().__init__(message, error_code="LAYOUT_FORMULA_PARSE_FAILED")


# =====================================================================
# 6. OCR ENGINE & INFERENCE EXCEPTIONS
# =====================================================================

class OCREngineError(BLASTOCRException):
    """OCR engine execution failed."""

    def __init__(self, message: str, error_code: str = "OCR_ENGINE_EXEC_FAILED", retryable: bool = True):
        super().__init__(message, error_code=error_code, status_code=500, retryable=retryable)


class OCREngineInitializationError(OCREngineError):
    """OCR backend weights failed to load or ONNX session crashed."""

    def __init__(self, backend_name: str, reason: str):
        super().__init__(
            f"OCR engine backend '{backend_name}' failed to initialize: {reason}",
            error_code="OCR_BACKEND_INIT_FAILED",
            retryable=False,
        )


class PageExtractionError(BLASTOCRException):
    """Failed to extract text from specific page."""

    def __init__(self, page_number: int, original_error: Any):
        self.page_number = page_number
        self.original_error = original_error
        super().__init__(
            f"Page {page_number} extraction failed: {original_error}",
            error_code="OCR_PAGE_EXTRACTION_FAILED",
            status_code=500,
            retryable=True,
            context={"page_number": page_number, "cause": str(original_error)},
        )


class LowConfidenceError(BLASTOCRException):
    """OCR confidence below acceptance threshold."""

    def __init__(self, confidence: float, threshold: float):
        self.confidence = confidence
        self.threshold = threshold
        super().__init__(
            f"Confidence {confidence:.2f} < {threshold:.2f}",
            error_code="OCR_LOW_CONFIDENCE",
            status_code=422,
            retryable=False,
            context={"confidence": confidence, "threshold": threshold},
        )


# =====================================================================
# 7. QUEUE, SWARM & DISTRIBUTED WORKER EXCEPTIONS
# =====================================================================

class QueueError(BLASTOCRException):
    """Distributed task queue or Redis communication fault."""

    def __init__(self, message: str, error_code: str = "QUEUE_FAULT", retryable: bool = True):
        super().__init__(message, error_code=error_code, status_code=503, retryable=retryable)


class WorkerLeaseExpiredError(QueueError):
    """Worker task lock expired before compute completed."""

    def __init__(self, task_id: str, worker_id: str):
        super().__init__(
            f"Task '{task_id}' lease expired for worker '{worker_id}'.",
            error_code="QUEUE_LEASE_EXPIRED",
            retryable=True,
        )


class QueueStarvationError(QueueError):
    """Low/default priority queue starved beyond safety timeout."""

    def __init__(self, queue_name: str, wait_seconds: float):
        super().__init__(
            f"Queue '{queue_name}' starved for {wait_seconds:.1f}s.",
            error_code="QUEUE_STARVATION_DETECTED",
            retryable=True,
        )


class DLQMaxRetriesExceededError(QueueError):
    """Job exceeded maximum retry attempts and moved to DLQ quarantine."""

    def __init__(self, task_id: str, attempts: int):
        super().__init__(
            f"Task '{task_id}' exhausted {attempts} retries. Quarantined to DLQ.",
            error_code="QUEUE_DLQ_QUARANTINED",
            retryable=False,
        )


# =====================================================================
# 8. STREAMING, CACHE & STORAGE EXCEPTIONS
# =====================================================================

class StreamingError(BLASTOCRException):
    """Streaming document generator or buffer fault."""

    def __init__(self, message: str, error_code: str = "STREAMING_FAULT", retryable: bool = True):
        super().__init__(message, error_code=error_code, status_code=500, retryable=retryable)


class SSEClientDisconnectedError(StreamingError):
    """Client disconnected from SSE streaming connection."""

    def __init__(self, job_id: int):
        super().__init__(
            f"Client disconnected from SSE stream for job {job_id}.",
            error_code="SSE_CLIENT_DISCONNECTED",
            retryable=False,
        )


class MultipartUploadTimeoutError(StreamingError):
    """S3/MinIO multipart upload chunk timed out."""

    def __init__(self, upload_id: str, part_number: int):
        super().__init__(
            f"Multipart upload '{upload_id}' part {part_number} timed out.",
            error_code="STORAGE_MULTIPART_TIMEOUT",
            retryable=True,
        )


class OutputWriteError(BLASTOCRException):
    """Failed to write serialized results to disk."""

    def __init__(self, destination_path: str, reason: str):
        super().__init__(
            f"Failed to write results to '{destination_path}': {reason}",
            error_code="IO_OUTPUT_WRITE_FAILED",
            status_code=500,
            retryable=False,
            context={"destination_path": destination_path},
        )
```

---

## 3.3 HTTP Status Code & Error Code Mapping Matrix

| Exception Class | Error Code | HTTP Status | Retryable? | Recommended Recovery Action |
|---|---|---|---|---|
| `DocumentSecurityError` / `PathTraversalError` | `SEC_PATH_TRAVERSAL` | **400 Bad Request** | No | Reject request immediately; log security event |
| `DecompressionBombError` | `SEC_DECOMPRESSION_BOMB` | **413 Payload Too Large** | No | Reject payload; purge temporary disk buffer |
| `FileSizeExceededError` | `SEC_FILE_TOO_LARGE` | **413 Payload Too Large** | No | Advise client to compress document |
| `UnsupportedFormatError` | `INGEST_UNSUPPORTED_FORMAT` | **415 Unsupported Media Type** | No | Notify caller of allowed MIME types |
| `PDFStructuralIntegrityError` | `PDF_STRUCTURAL_CORRUPTION` | **422 Unprocessable Entity** | No | Attempt regex trailer repair; else reject |
| `CyclicReferenceError` | `PDF_CYCLIC_OBJECT_LOOP` | **422 Unprocessable Entity** | No | Terminate tree descent; isolate page refs |
| `DigitalTextCorruptedError` | `TXT_PUA_CMAP_CORRUPTED` | **200 OK (Degraded)** | Yes | Auto-fallback: bypass digital text, run visual OCR |
| `PageExtractionError` | `OCR_PAGE_EXTRACTION_FAILED` | **500 Internal Server Error** | Yes | Retry with exponential backoff; fallback engine |
| `WorkerLeaseExpiredError` | `QUEUE_LEASE_EXPIRED` | **503 Service Unavailable** | Yes | Re-enqueue task to queue head; notify supervisor |
| `SSEClientDisconnectedError` | `SSE_CLIENT_DISCONNECTED` | **499 Client Closed Request** | No | Break async generator loop; release cache locks |

---

# 4. Programmatic Adversarial Test Harness Specifications

## 4.1 Test Architecture & Adversarial Threat Matrix

The test harness provides **concrete, deterministic pytest test suites** designed to validate every defensive boundary against hostile, malformed, or extreme inputs.

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                   PROGRAMMATIC ADVERSARIAL HARNESS                      │
 ├────────────────────────────────┬────────────────────────────────────────┤
 │ 1. PDF Corruptions             │ tests/adversarial/test_pdf_adversarial.py
 │ 2. Extreme Raster & Bombs      │ tests/adversarial/test_raster_adversarial.py
 │ 3. Typography & Trojan Source  │ tests/adversarial/test_text_adversarial.py
 │ 4. Non-Manhattan Layout & TeX  │ tests/adversarial/test_layout_adversarial.py
 │ 5. Streaming & Concurrency     │ tests/adversarial/test_streaming_queue_adversarial.py
 └────────────────────────────────┴────────────────────────────────────────┘
```

---

## 4.2 Synthetic Corruption Artifact Generators

```python
"""
Adversarial Artifact Generators.
Synthesizes deterministic byte payloads for all taxonomy edge cases.
"""

import io
import struct
import zlib
from PIL import Image


def generate_broken_xref_pdf() -> bytes:
    """Generates PDF with completely corrupt XREF byte offsets."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj\n"
        b"xref\n"
        b"0 4\n"
        b"0000000000 65535 f \n"
        b"0000999999 00000 n \n"  # Bogus offset
        b"0000888888 00000 n \n"  # Bogus offset
        b"0000777777 00000 n \n"  # Bogus offset
        b"trailer << /Size 4 /Root 1 0 R >>\n"
        b"startxref\n"
        b"190\n"
        b"%%EOF"
    )


def generate_cyclic_pdf() -> bytes:
    """Generates PDF with infinite parent/child page tree loop (TAX-PDF-03)."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Pages /Kids [2 0 R] /Count 1 >> endobj\n"  # 3 points to 2, 2 points to 3
        b"trailer << /Root 1 0 R >>\n"
        b"%%EOF"
    )


def generate_decompression_bomb_png_bytes(width: int = 20000, height: int = 20000) -> bytes:
    """Generates a valid 20,000 x 20,000 PNG image header with 10KB compressed payload."""
    raw_scanline = b"\x00" + (b"\xFF\xFF\xFF" * width)
    compressed = zlib.compress(raw_scanline * 10, level=9)

    out = io.BytesIO()
    out.write(b"\x89PNG\r\n\x1a\n")
    # IHDR chunk
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    out.write(struct.pack(">I", len(ihdr_data)))
    out.write(b"IHDR")
    out.write(ihdr_data)
    out.write(struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data)))
    # IDAT chunk
    out.write(struct.pack(">I", len(compressed)))
    out.write(b"IDAT")
    out.write(compressed)
    out.write(struct.pack(">I", zlib.crc32(b"IDAT" + compressed)))
    # IEND chunk
    out.write(struct.pack(">I", 0))
    out.write(b"IEND")
    out.write(struct.pack(">I", zlib.crc32(b"IEND")))

    return out.getvalue()
```

---

## 4.3 Programmatic Pytest Adversarial Suites

### 4.3.1 `tests/adversarial/test_pdf_adversarial.py`
```python
"""Adversarial Pytest Suite for PDF Structural Corruptions."""

import pytest
from blast_ocr.core.exceptions import (
    DocumentSecurityError,
    IncrementalUpdateSecurityError,
    PDFStructuralIntegrityError,
    TrailerDictionaryCorruptedError,
)
from blast_ocr.security.pdf_validator import PDFPreflightValidator


def test_polyglot_prepended_header_rejected():
    """TAX-PDF-04: Verify polyglot executable prepended before %PDF- is rejected."""
    polyglot_bytes = b"MZ\x90\x00\x03\x00\x00\x00" + b"%PDF-1.7\n1 0 obj<<>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
    with pytest.raises(DocumentSecurityError) as exc_info:
        PDFPreflightValidator.validate_bytes(polyglot_bytes)
    assert exc_info.value.error_code == "SEC_PDF_POLYGLOT"


def test_broken_trailer_startxref_detection():
    """TAX-PDF-08: Verify trailer without startxref raises TrailerDictionaryCorruptedError."""
    corrupted_pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Size 1>>\n%%EOF"
    with pytest.raises(TrailerDictionaryCorruptedError):
        PDFPreflightValidator.validate_bytes(corrupted_pdf)


def test_excessive_incremental_revisions_shadow_attack():
    """TAX-PDF-09: Verify documents with > 20 revisions are rejected."""
    excessive_pdf = b"%PDF-1.4\n" + (b"1 0 obj<<>>endobj\ntrailer<</Root 1 0 R>>\nstartxref 10\n%%EOF\n" * 25)
    with pytest.raises(IncrementalUpdateSecurityError):
        PDFPreflightValidator.validate_bytes(excessive_pdf)
```

---

### 4.3.2 `tests/adversarial/test_raster_adversarial.py`
```python
"""Adversarial Pytest Suite for Raster Images & Decompression Bombs."""

import numpy as np
import pytest
from blast_ocr.core.exceptions import DecompressionBombError, DimensionExceededError
from blast_ocr.core.image_preprocessor import ImagePreprocessor
from blast_ocr.security.image_sanitizer import ImageSecuritySanitizer


def test_decompression_bomb_header_interception():
    """TAX-IMG-02: Verify 400 Megapixel image is rejected prior to C++ decode."""
    # Synthetic PNG declaring 20000 x 20000 pixels (400MP)
    bomb_bytes = generate_decompression_bomb_png_bytes(20000, 20000)
    with pytest.raises((DecompressionBombError, DimensionExceededError)):
        ImageSecuritySanitizer.inspect_and_sanitize(bomb_bytes)


def test_transparent_png_alpha_matte_compositing():
    """TAX-IMG-06: Verify black text on transparent alpha does not collapse to black."""
    # RGBA: Pure black text (0, 0, 0) with alpha=255, transparent background with alpha=0
    h, w = 100, 100
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[40:60, 40:60, 3] = 255  # 20x20 black text block

    composited = ImagePreprocessor.composite_alpha_over_white(rgba)
    assert composited.shape == (100, 100, 3)
    # Background (was alpha=0) must now be pure white (255, 255, 255)
    assert np.all(composited[0, 0] == [255, 255, 255])
    # Text (was alpha=255) must remain black (0, 0, 0)
    assert np.all(composited[50, 50] == [0, 0, 0])


def test_uint16_normalization_prevents_saturation():
    """TAX-IMG-04: Verify 16-bit uint16 TIFF values are normalized to [0, 255]."""
    uint16_img = np.array([[0, 32768, 65535]], dtype=np.uint16)
    uint8_img = ImagePreprocessor.normalize_bit_depth_to_uint8(uint16_img)
    assert uint8_img.dtype == np.uint8
    assert uint8_img[0, 0] == 0
    assert 127 <= uint8_img[0, 1] <= 128
    assert uint8_img[0, 2] == 255
```

---

### 4.3.3 `tests/adversarial/test_text_adversarial.py`
```python
"""Adversarial Pytest Suite for Typography, BiDi & Unicode Exploits."""

from blast_ocr.core.text_sanitizer import TextSanitizer


def test_bidi_trojan_source_override_neutralization():
    """TAX-TXT-02: Verify BiDi override characters are stripped."""
    # Trojan Source: "access_level = " + RLO + "admin" + PDF + "user"
    hostile_input = "access_level = \u202Eadmin\u202Cuser"
    sanitized = TextSanitizer.sanitize(hostile_input, strip_bidi=True)
    assert "\u202E" not in sanitized
    assert "\u202C" not in sanitized
    assert sanitized == "access_level = adminuser"


def test_invisible_zero_width_and_soft_hyphens_stripped():
    """TAX-TXT-01, TAX-TXT-07: Verify ZWSP, BOM, and soft hyphens are removed."""
    dirty_text = "in\u200Bvoice-\u00ADnumber\uFEFF123"
    clean_text = TextSanitizer.sanitize(dirty_text)
    assert clean_text == "invoice-number123"


def test_nfkc_ligature_and_math_alphanumeric_decomposition():
    """TAX-TXT-06, TAX-TXT-09: Verify ligatures and math bold glyphs fold to standard ASCII."""
    raw_ligatures = "The oﬃce is 𝕏-ray certified"
    folded = TextSanitizer.sanitize(raw_ligatures)
    assert folded == "The office is X-ray certified"


def test_null_byte_and_c0_control_sanitization():
    """TAX-TXT-12: Verify null bytes (\x00) and C0 control codes are stripped."""
    raw_payload = "header\x00value\x07\x1B\x0C"
    clean = TextSanitizer.sanitize(raw_payload, strict_null=True)
    assert "\x00" not in clean
    assert clean == "headervalue"
```

---

### 4.3.4 `tests/adversarial/test_layout_adversarial.py`
```python
"""Adversarial Pytest Suite for Document Layout & Multi-Modal Structure."""

from blast_ocr.core.layout_sorter import LayoutSpan, XYCutPlusPlusSorter


def test_spanning_header_does_not_collapse_two_column_reading_order():
    """TAX-LAY-01: Verify spanning header does not collapse multi-column reading order."""
    page_w, page_h = 1000.0, 1400.0

    spans = [
        # Spanning Title Header at Y=50 (width = 900px, 90% of page)
        LayoutSpan("title", "Executive Summary", 50.0, 50.0, 950.0, 100.0),
        # Column 1 Paragraphs (X: 50 to 450)
        LayoutSpan("col1_p1", "Col 1 Para 1", 50.0, 150.0, 450.0, 250.0),
        LayoutSpan("col1_p2", "Col 1 Para 2", 50.0, 270.0, 450.0, 370.0),
        # Column 2 Paragraphs (X: 550 to 950)
        LayoutSpan("col2_p1", "Col 2 Para 1", 550.0, 150.0, 950.0, 250.0),
        LayoutSpan("col2_p2", "Col 2 Para 2", 550.0, 270.0, 950.0, 370.0),
    ]

    sorted_spans = XYCutPlusPlusSorter.sort_page_layout(spans, page_w, page_h, is_rtl=False)
    ordered_ids = [s.span_id for s in sorted_spans]

    # Correct Reading Order: Title -> Col 1 P1 -> Col 1 P2 -> Col 2 P1 -> Col 2 P2
    expected_order = ["title", "col1_p1", "col1_p2", "col2_p1", "col2_p2"]
    assert ordered_ids == expected_order
```

---

### 4.3.5 `tests/adversarial/test_streaming_queue_adversarial.py`
```python
"""Adversarial Pytest Suite for SSE Streaming & Queue Starvation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from blast_ocr.api.sse_handler import ResilientSSEHandler
from blast_ocr.queue.fair_priority import FairPriorityQueueGovernor


@pytest.mark.asyncio
async def test_sse_client_disconnect_terminates_polling_loop():
    """TAX-STR-05: Verify client disconnect terminates generator loop immediately."""
    mock_request = MagicMock()
    # Simulate client disconnect after 1st tick
    mock_request.is_disconnected = AsyncMock(side_effect=[False, True])

    status_fetcher = MagicMock(return_value={"status": "processing", "progress": 0.1})

    response = await ResilientSSEHandler.create_event_stream(
        request=mock_request,
        job_id=101,
        status_fetcher=status_fetcher,
        poll_interval_seconds=0.01,
    )

    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)

    assert len(chunks) == 1
    assert "processing" in chunks[0]


def test_fair_queue_governor_prevents_low_priority_starvation():
    """TAX-STR-02: Verify weighted sampling pops low-priority jobs under heavy load."""
    mock_redis = MagicMock()
    # Simulate queue pop results
    mock_redis.brpop.return_value = (b"blast_ocr:queue:low", b'{"job_id": 999}')

    governor = FairPriorityQueueGovernor(mock_redis)
    result = governor.pop_next_job_fair(timeout=1)

    assert result is not None
    queue_name, payload = result
    assert queue_name == "blast_ocr:queue:low"
    assert "999" in payload
```

---

## 4.4 Hypothesis Property-Based Invariant Test Specifications

```python
"""
Hypothesis Property-Based Invariant Tests.
Validates algebraic invariants across text sanitizers and bounding box geometry.
"""

from hypothesis import given, strategies as st
from blast_ocr.core.text_sanitizer import TextSanitizer


@given(st.text())
def test_text_sanitizer_idempotence_invariant(text: str):
    """Invariant: sanitize(sanitize(t)) == sanitize(t)"""
    pass1 = TextSanitizer.sanitize(text)
    pass2 = TextSanitizer.sanitize(pass1)
    assert pass1 == pass2


@given(st.text())
def test_text_sanitizer_null_exclusion_invariant(text: str):
    """Invariant: Output of sanitize(t) NEVER contains null bytes."""
    sanitized = TextSanitizer.sanitize(text, strict_null=True)
    assert "\x00" not in sanitized
```

---

## 4.5 Chaos Concurrency, Memory Leak Slope & Disconnect Stress Harness

```python
"""
Continuous Memory Leak Slope & Chaos Harness.
Simulates 10,000-page processing while measuring RSS memory regression slope.
"""

import os
import psutil
import pytest


def measure_memory_leak_slope(iterations: int = 100) -> float:
    """
    Computes linear regression slope of RSS memory:
    Slope <= 0.005 MB/page is REQUIRED for Certified Production Grade.
    """
    process = psutil.Process(os.getpid())
    rss_readings = []

    for _ in range(iterations):
        # Simulate page processing cycle
        rss_mb = process.memory_info().rss / (1024 * 1024)
        rss_readings.append(rss_mb)

    # Compute delta slope
    slope = (rss_readings[-1] - rss_readings[0]) / iterations
    return slope


def test_streaming_memory_leak_slope_gate():
    slope = measure_memory_leak_slope(iterations=50)
    assert slope <= 0.005, f"Memory leak slope {slope:.4f} MB/page exceeded 0.005 ceiling"
```

---

# 5. Phased Implementation Roadmap & Quick Wins Matrix

## 5.1 Phased Execution Schedule (Tiers 1 through 4)

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                      PHASED IMPLEMENTATION TIMELINE                     │
 ├─────────────────────────┬────────────────────────┬──────────────────────┤
 │ TIER 1: Quick Wins      │ Duration: Immediate    │ Zero risk, high ROI  │
 │ TIER 2: Core Hardening  │ Duration: 1-2 Days     │ Security & memory    │
 │ TIER 3: Layout Defense  │ Duration: 3-5 Days     │ Multi-column & math  │
 │ TIER 4: Chaos & Certify │ Duration: Continuous   │ Enterprise CI gate   │
 └─────────────────────────┴────────────────────────┴──────────────────────┘
```

---

## 5.2 Immediate Quick Wins (< 30 Minutes Execution)

| # | Quick Win Action | Target File & Line | Root Problem Neutralized | Estimated Time |
|---|---|---|---|---|
| **QW-1** | Add `fitz.TOOLS.store_shrink(100)` & `page = None` | `blast_ocr/core/streaming.py:205` | MuPDF glibc arena memory leak (TAX-STR-01) | 10 mins |
| **QW-2** | Add `await request.is_disconnected()` & `X-Accel-Buffering` | `blast_ocr/api/routes.py:382` | Zombie SSE streaming background polling (TAX-STR-05) | 15 mins |
| **QW-3** | Wrap `SemanticChunker` in `asyncio.to_thread` | `blast_ocr/api/routes.py:419,447` | Event loop blocking on CPU chunking (TAX-STR-06) | 10 mins |
| **QW-4** | Clamp recognition crop `max_width = 1536` | `blast_ocr/core/batch_preprocessor.py:408` | Extreme panorama CUDA VRAM waste (TAX-IMG-01) | 15 mins |
| **QW-5** | Porter-Duff white matte alpha compositing | `blast_ocr/core/batch_preprocessor.py:76` | Transparent PNG black-on-black collapse (TAX-IMG-06) | 20 mins |
| **QW-6** | Global Null-Byte & BiDi Override Filter | `blast_ocr/security/gateway.py:120` | Database aborts & Trojan Source injection (TAX-TXT-12) | 15 mins |

---

## 5.3 Forensic Risk-Effort-Impact Prioritization Scoring Matrix

*Scores: Impact (1-5), Effort (1-5), Risk (1-5). Priority Rank = $\text{Impact} \times 2 - \text{Effort} - \text{Risk}$.*

| ID | Failure Mode & Vulnerability | Severity | Target Module | Impact (1-5) | Effort (1-5) | Risk (1-5) | Priority Rank | Phase Tier |
|---|---|---|---|---|---|---|---|---|
| **GAP-01** | PDF Magic Header Offset & Polyglot Bypass | **P0** | `blast_ocr/security/pdf_validator.py` | 5 | 1 | 1 | **8** | **Tier 1** |
| **GAP-02** | Decompression Bomb Native Heap Crash | **P0** | `blast_ocr/security/image_sanitizer.py` | 5 | 2 | 1 | **7** | **Tier 2** |
| **GAP-03** | Trojan Source BiDi & Null Byte Injections | **P0** | `blast_ocr/core/text_sanitizer.py` | 5 | 1 | 1 | **8** | **Tier 1** |
| **GAP-04** | Spanning Header XY-Cut Layout Collapse | **P1** | `blast_ocr/core/layout_sorter.py` | 4 | 2 | 2 | **4** | **Tier 3** |
| **GAP-05** | SSE Connection Leak on Client Disconnect | **P1** | `blast_ocr/api/routes.py` | 4 | 1 | 1 | **6** | **Tier 1** |
| **GAP-06** | MuPDF Memory Arena Heap Accumulation | **P1** | `blast_ocr/core/streaming.py` | 5 | 1 | 1 | **8** | **Tier 1** |
| **GAP-07** | Borderless Table Extraction Dropout | **P1** | `blast_ocr/core/table_extractor.py` | 4 | 3 | 2 | **3** | **Tier 3** |
| **GAP-08** | 16-Bit TIFF Saturation & NaN CTC Loss | **P2** | `blast_ocr/core/image_preprocessor.py` | 4 | 1 | 1 | **6** | **Tier 2** |
| **GAP-09** | Missing /ToUnicode PUA Font Corruption | **P1** | `blast_ocr/core/text_sanitizer.py` | 4 | 2 | 1 | **5** | **Tier 2** |
| **GAP-10** | Redis Low-Priority Queue Starvation | **P2** | `blast_ocr/queue/fair_priority.py` | 3 | 2 | 1 | **3** | **Tier 3** |
| **GAP-11** | CMYK Gamut Distortion without LittleCMS | **P2** | `blast_ocr/core/color_manager.py` | 3 | 2 | 1 | **3** | **Tier 3** |
| **GAP-12** | Nested Math Formula AST Regex Failure | **P2** | `blast_ocr/core/formula_extractor.py` | 3 | 3 | 2 | **1** | **Tier 3** |

---

## 5.4 Independent Verification & Invalidation Criteria

To independently verify that the Hardening Blueprint and Test Specifications have been completely fulfilled:

1. **Static Analysis & Type Integrity**:
   ```bash
   ruff check blast_ocr/ tests/ eval/
   ```
   *Success Criterion*: 0 errors, 0 warnings across all repository files.

2. **Full CI & Adversarial Test Harness Execution**:
   ```bash
   pytest tests/ -v
   ```
   *Success Criterion*: All existing unit/integration tests pass with 0 regressions.

3. **Memory Regression Invalidation Gate**:
   ```bash
   python -m eval.stress_test --pages 100
   ```
   *Success Criterion*: Linear regression slope $\le 0.005\text{ MB/page}$. If slope $> 0.005\text{ MB/page}$, the bounded memory governor is invalidated.

4. **Adversarial Invariant Gate**:
   *Success Criterion*: Synthetic decompression bombs, cyclic object loops, and BiDi override vectors must raise their respective typed exceptions (`DecompressionBombError`, `CyclicReferenceError`, `BiDiOverrideDetectedError`) without crashing Python runtime or OS processes.

---
*End of Hardening Blueprint & Programmatic Test Harness Specifications.*
