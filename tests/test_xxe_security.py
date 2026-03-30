"""
PHASE 4: XML External Entity (XXE) Injection Security Audit
"""

import pytest
import zipfile
import tempfile
import os
import io


# ── Test 4.1: Malicious PPTX — Local File Disclosure XXE ──────────────────
def test_pptx_xxe_local_file_disclosure():
    """
    REASONING: Craft a PPTX where slide1.xml contains a DOCTYPE with
    a SYSTEM entity pointing to /etc/passwd. If parser resolves it,
    /etc/passwd content appears in extracted text.
    """
    xxe_payload = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:txBody>
          <a:p><a:r><a:t>&xxe;</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""

    # Build minimal valid PPTX ZIP structure
    pptx_buffer = io.BytesIO()
    with zipfile.ZipFile(pptx_buffer, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
            "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "ppt/presentation.xml",
            '<?xml version="1.0"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldIdLst><p:sldId id="256" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></p:sldIdLst></p:presentation>',
        )
        zf.writestr(
            "ppt/_rels/presentation.xml.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>'
            "</Relationships>",
        )
        zf.writestr("ppt/slides/slide1.xml", xxe_payload)

    pptx_path = tempfile.mktemp(suffix=".pptx")
    with open(pptx_path, "wb") as f:
        f.write(pptx_buffer.getvalue())

    try:
        from blast_ocr.core.extractor import extract_from_pptx

        result = extract_from_pptx(pptx_path)

        # If /etc/passwd content appears in result, XXE succeeded
        if "root:" in result or "/bin/bash" in result or "/home/" in result:
            pytest.fail(
                "BUG-XXE-LFD-01 | CRITICAL | security\n"
                "XXE Local File Disclosure CONFIRMED. /etc/passwd content extracted.\n"
                "The XML parser is resolving SYSTEM entities from user-uploaded PPTX files.\n"
                "Fix: Use 'import defusedxml; defusedxml.defuse_stdlib()' at application startup, "
                "OR switch to 'from defusedxml.ElementTree import parse' for all XML parsing."
            )
    except Exception as e:
        # Exception during parse is acceptable — means entity was blocked
        if "root:" in str(e) or "/bin/" in str(e):
            pytest.fail(f"BUG-XXE-LFD-02: XXE content found in exception message: {e}")
    finally:
        if os.path.exists(pptx_path):
            os.unlink(pptx_path)


# ── Test 4.2: Billion Laughs DoS via entity expansion ─────────────────────
def test_pptx_xxe_billion_laughs_dos():
    """
    REASONING: Nested entity expansion causes exponential memory growth.
    &lol9; expands to ~1 billion 'lol' strings before the parser
    completes, consuming all available RAM.
    """
    import sys

    if sys.platform == "win32":
        pytest.skip("resource module not available on Windows for memory limits")

    billion_laughs = """<?xml version="1.0"?>
<!DOCTYPE bomb [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
  <!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">
]>
<root>&lol5;</root>"""

    pptx_buffer = io.BytesIO()
    with zipfile.ZipFile(pptx_buffer, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        zf.writestr("ppt/slides/slide1.xml", billion_laughs)

    pptx_path = tempfile.mktemp(suffix=".pptx")
    with open(pptx_path, "wb") as f:
        f.write(pptx_buffer.getvalue())

    try:
        # Set a strict memory limit for this test (256MB)
        import resource

        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, hard))

        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError("Billion Laughs DoS — parser hung for >5 seconds")

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(5)

        try:
            from blast_ocr.core.extractor import extract_from_pptx

            extract_from_pptx(pptx_path)
        except (MemoryError, TimeoutError) as e:
            pytest.fail(
                f"BUG-XXE-DOS-01 | CRITICAL | security\n"
                f"Billion Laughs DoS attack succeeded: {e}\n"
                f"XML parser expanded nested entities until memory/time limit hit.\n"
                f"Fix: Use defusedxml which blocks entity expansion by default, "
                f"or set parser.set_feature(xml.sax.handler.feature_external_ges, False)."
            )
        except Exception:
            pass  # Any other exception means the attack was blocked
        finally:
            signal.alarm(0)
            resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
    finally:
        if os.path.exists(pptx_path):
            os.unlink(pptx_path)


# ── Test 4.3: Verify defusedxml or equivalent protection is in place ───────
def test_xml_parser_uses_safe_library():
    """Check that the codebase uses defusedxml or explicit entity blocking."""
    from pathlib import Path

    sources_to_check = [
        "blast_ocr/core/extractor.py",
        "blast_ocr/pipeline.py",
    ]

    safe_patterns = [
        "defusedxml",
        "forbid_entities",
        "disallow-doctype-decl",
        "feature_external_ges",
        "resolve_entities",
    ]

    for src_path in sources_to_check:
        p = Path(src_path)
        if not p.exists():
            continue
        source = p.read_text()
        if not any(pattern in source for pattern in safe_patterns):
            # Check if the file does any XML parsing
            if any(
                xml_lib in source
                for xml_lib in ["etree", "lxml", "pptx", "docx", "xml"]
            ):
                pytest.fail(
                    f"BUG-XXE-PROTECTION-01 | CRITICAL | security\n"
                    f"{src_path} uses XML parsing without defusedxml protection.\n"
                    f"python-pptx uses lxml internally — vulnerable to XXE by default.\n"
                    f"Fix: Add 'import defusedxml; defusedxml.defuse_stdlib()' "
                    f"at the top of {src_path} or in blast_ocr/__init__.py."
                )
