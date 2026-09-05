"""Automated Marketing Loops Engine.

Autonomous marketing loop orchestrator based on the marketing-loops skill.
Runs scheduled, repeatable marketing checks across SEO, competitor intel,
internal linking, and content freshness with stateful idempotency.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

STATE_FILE = Path("data/marketing_loops_state.json")


def _load_state() -> Dict[str, Any]:
    """Load loop execution state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: Dict[str, Any]) -> None:
    """Persist loop execution state to disk."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def check_keyword_gaps() -> Dict[str, Any]:
    """Weekly keyword gap loop: identify uncovered search queries."""
    target_queries = [
        "high throughput pdf ocr python",
        "extract tables from scanned pdf python",
        "pdf ocr memory leak prevention",
        "mcp server ocr setup guide",
        "local ocr vs cloud vision cost comparison",
        "searchable pdf sandwich generation",
        "distributed ocr worker swarm redis",
        "pdf to markdown python",
        "scanned pdf to docx python",
        "pptx to markdown python",
        "image to searchable pdf python",
        "pdf to latex python",
        "scanned pdf to epub python",
        "blast vs tesseract",
        "blast vs easyocr",
        "blast vs aws textract",
        "blast vs docling",
        "blast vs marker",
        "tesseract alternative",
        "aws textract alternative",
    ]
    docs_dir = Path("docs")
    covered_files = list(docs_dir.rglob("*.md")) if docs_dir.exists() else []
    all_text = " ".join([f.read_text(encoding="utf-8", errors="ignore").lower() for f in covered_files])

    gaps = [q for q in target_queries if q not in all_text]
    return {
        "loop": "keyword-gap",
        "status": "healthy" if not gaps else "action_needed",
        "total_monitored_queries": len(target_queries),
        "uncovered_gaps_count": len(gaps),
        "uncovered_queries": gaps,
    }


def check_internal_linking() -> Dict[str, Any]:
    """Weekly internal linking loop: verify cross-links between guides and hubs."""
    docs_dir = Path("docs")
    if not docs_dir.exists():
        return {"loop": "internal-linking", "status": "no_docs_dir", "orphans": []}

    md_files = [f for f in docs_dir.rglob("*.md") if f.is_file()]
    # Fast single-pass in-memory cache
    cached_texts = {f: f.read_text(encoding="utf-8", errors="ignore") for f in md_files}
    orphans: List[str] = []

    for file_path, _ in cached_texts.items():
        base_name = file_path.name
        if base_name in ["index.md", "README.md"]:
            continue
        rel_str = str(file_path.relative_to(docs_dir.parent))
        is_linked = any(
            (base_name in txt or rel_str in txt)
            for other_path, txt in cached_texts.items()
            if other_path != file_path
        )
        if not is_linked:
            orphans.append(rel_str)

    return {
        "loop": "internal-linking",
        "status": "healthy" if len(orphans) <= 10 else "action_needed",
        "monitored_docs": len(md_files),
        "orphan_count": len(orphans),
        "orphan_candidates": orphans[:10],
    }


def check_programmatic_seo_quality() -> Dict[str, Any]:
    """Monthly programmatic SEO quality check: ensure JSON-LD and direct answers."""
    conv_dir = Path("docs/conversions")
    comp_dir = Path("docs/comparisons")
    seo_dir = Path("docs/seo")

    checked = 0
    missing_json_ld = []
    missing_author = []

    for folder in [conv_dir, comp_dir, seo_dir]:
        if not folder.exists():
            continue
        for doc in folder.glob("*.md"):
            if doc.name == "index.md":
                continue
            checked += 1
            content = doc.read_text(encoding="utf-8", errors="ignore")
            if "@context" not in content:
                missing_json_ld.append(str(doc))
            if "ibrahimsalman.vercel.app" not in content:
                missing_author.append(str(doc))

    return {
        "loop": "programmatic-seo-quality",
        "status": "healthy" if not missing_json_ld and not missing_author else "action_needed",
        "total_pages_checked": checked,
        "missing_json_ld_count": len(missing_json_ld),
        "missing_author_count": len(missing_author),
        "flags": missing_json_ld + missing_author,
    }


def run_loops(loop_name: str = "all", dry_run: bool = False) -> Dict[str, Any]:
    """Execute marketing loops with state persistence."""
    state = _load_state()
    now_iso = datetime.now(timezone.utc).isoformat()

    results: Dict[str, Any] = {}

    if loop_name in ["all", "keyword-gap"]:
        res = check_keyword_gaps()
        results["keyword-gap"] = res
        if not dry_run:
            state["keyword-gap"] = {"last_run": now_iso, "status": res["status"]}

    if loop_name in ["all", "internal-linking"]:
        res = check_internal_linking()
        results["internal-linking"] = res
        if not dry_run:
            state["internal-linking"] = {"last_run": now_iso, "status": res["status"]}

    if loop_name in ["all", "programmatic-seo"]:
        res = check_programmatic_seo_quality()
        results["programmatic-seo"] = res
        if not dry_run:
            state["programmatic-seo"] = {"last_run": now_iso, "status": res["status"]}

    if not dry_run:
        _save_state(state)

    return {
        "timestamp": now_iso,
        "dry_run": dry_run,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run autonomous marketing loops.")
    parser.add_argument(
        "--loop",
        choices=["all", "keyword-gap", "internal-linking", "programmatic-seo"],
        default="all",
        help="Marketing loop to trigger (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate loop run without updating state file",
    )
    args = parser.parse_args()
    report = run_loops(loop_name=args.loop, dry_run=args.dry_run)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
