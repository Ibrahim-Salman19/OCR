#!/usr/bin/env python3
"""B.L.A.S.T. OCR evaluation harness (Phase 0).

Runs each gold page through the same forensic-restoration step
production applies (blast_ocr.core.worker.restore_page_image) and then
the extractor directly (bypassing the on-disk result cache, so eval runs
are never poisoned by a stale cached answer) against the hand-transcribed
gold corpus in eval/gold/, scores CER, WER, and reading-order agreement,
runs any fact checks defined in eval/facts/, and writes a reproducible
scorecard to eval/results/<git-sha>.json.

Usage:
    python eval/run.py                     # full corpus, default engine
    python eval/run.py --pages p020,p095   # a subset, by gold page id
    python eval/run.py --no-save           # print only
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import yaml

from eval.gold_loader import GoldRecord, load_all_gold
from eval.metrics import compute_cer, compute_wer, reading_order_tau, run_fact_checks

GOLD_DIR = REPO_ROOT / "eval" / "gold"
FACTS_DIR = REPO_ROOT / "eval" / "facts"
PAGES_DIR = REPO_ROOT / "eval" / "pages"
RESULTS_DIR = REPO_ROOT / "eval" / "results"

SCHEMA_VERSION = 1


def git_sha() -> str:
    # Generous timeout: this repo is commonly checked out on a mounted
    # NTFS drive under WSL, where `git status` walking large untracked
    # directories (poppler-*, caches) can take several seconds, especially
    # under concurrent disk I/O (e.g. a model download running alongside).
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        sha = rev.stdout.strip() or "unknown"
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if status.stdout.strip():
            sha += "-dirty"
        return sha
    except Exception:
        return "unknown"


def get_extractor(engine: str):
    from blast_ocr.core.engines import get_engine
    return get_engine(engine)


def run_one_page(extractor, gold: GoldRecord, image_path: Path, restore_dir: str) -> dict:
    # FIX(phase1): route through the same forensic-restoration step
    # production applies before OCR (blast_ocr.core.worker.restore_page_image,
    # mode="standard"), not the raw rendered page. Before this fix the
    # harness measured RobustOCRExtractor.process_page() in isolation,
    # which skipped ForensicRestorer.restore() entirely -- a real gap
    # between what this scorecard measured and what a user actually
    # experiences, discovered while wiring up restoration consistently
    # across pipeline.py's job types. See docs/EVAL_HARNESS.md.
    from blast_ocr.core.worker import restore_page_image

    restored_path = restore_page_image(str(image_path), restore_dir, mode="standard")

    # time.monotonic(), not time.time(): this harness runs in a sandboxed
    # dev environment (WSL2 on a machine that can suspend mid-run), and
    # wall-clock time.time() includes any host-suspend duration in the
    # delta -- observed once as a single page reporting ~30000s elapsed.
    # monotonic is the documented-correct tool for measuring elapsed
    # duration for exactly this reason (immune to clock/suspend jumps).
    t0 = time.monotonic()
    result = extractor.process_page(restored_path, 1)
    elapsed = time.monotonic() - t0

    hyp_text = result.get("text", "") or ""
    gold_flat = gold.flat_text

    cer = compute_cer(gold_flat, hyp_text)
    wer = compute_wer(gold_flat, hyp_text)
    tau = reading_order_tau(gold.tokens, hyp_text)

    facts_path = FACTS_DIR / f"{gold.page_id}.facts.yaml"
    fact_results = []
    if facts_path.exists():
        spec = yaml.safe_load(facts_path.read_text(encoding="utf-8"))
        fact_results = run_fact_checks(spec.get("checks", []), hyp_text)

    return {
        "page_id": gold.page_id,
        "cer": cer,
        "wer": wer,
        "reading_order_tau": tau,
        "engine_confidence": result.get("confidence", 0.0),
        "warning": result.get("warning"),
        "elapsed_sec": round(elapsed, 3),
        "hyp_chars": len(hyp_text),
        "gold_chars": len(gold_flat),
        "fact_checks": [
            {
                "type": r.check_type,
                "description": r.description,
                "passed": r.passed,
                "detail": r.detail,
            }
            for r in fact_results
        ],
        "fact_pass_count": sum(1 for r in fact_results if r.passed),
        "fact_total_count": len(fact_results),
    }


def build_aggregate(per_page: list) -> dict:
    n = len(per_page)
    taus = [p["reading_order_tau"] for p in per_page if p["reading_order_tau"] is not None]
    total_facts = sum(p["fact_total_count"] for p in per_page)
    passed_facts = sum(p["fact_pass_count"] for p in per_page)
    return {
        "mean_cer": (sum(p["cer"] for p in per_page) / n) if n else None,
        "mean_wer": (sum(p["wer"] for p in per_page) / n) if n else None,
        "mean_reading_order_tau": (sum(taus) / len(taus)) if taus else None,
        "pages_with_tau_signal": len(taus),
        "fact_pass_rate": (passed_facts / total_facts) if total_facts else None,
        "fact_pass_count": passed_facts,
        "fact_total_count": total_facts,
        "page_count": n,
    }


def print_report(scorecard: dict) -> None:
    agg = scorecard["aggregate"]
    n = agg["page_count"]
    print()
    print("=" * 72)
    print(f"AGGREGATE  ({n} pages, engine={scorecard['engine']}, sha={scorecard['git_sha']})")
    print("=" * 72)
    print(f"  mean CER              : {agg['mean_cer']:.4f}")
    print(f"  mean WER              : {agg['mean_wer']:.4f}")
    tau_str = (
        f"{agg['mean_reading_order_tau']:.4f}"
        if agg["mean_reading_order_tau"] is not None
        else "n/a"
    )
    print(f"  mean reading-order tau: {tau_str}  ({agg['pages_with_tau_signal']}/{n} pages had signal)")
    fact_str = f"{agg['fact_pass_rate'] * 100:.1f}%" if agg["fact_pass_rate"] is not None else "n/a"
    print(f"  fact-check pass rate  : {fact_str}  ({agg['fact_pass_count']}/{agg['fact_total_count']})")
    print("=" * 72)

    failing = [
        (p["page_id"], fc)
        for p in scorecard["per_page"]
        for fc in p["fact_checks"]
        if not fc["passed"]
    ]
    if failing:
        print()
        print("FAILING FACT CHECKS:")
        for page_id, fc in failing:
            print(f"  [{page_id}] {fc['description']}  -- {fc['detail']}")


def main() -> dict:
    ap = argparse.ArgumentParser(description="B.L.A.S.T. OCR eval harness (Phase 0)")
    ap.add_argument("--engine", default="rapidocr", choices=["easyocr", "rapidocr"])
    ap.add_argument(
        "--pages",
        default=None,
        help="comma-separated gold page ids (e.g. p020,p095); default = full corpus",
    )
    ap.add_argument("--no-save", action="store_true", help="print only, don't write a scorecard")
    ap.add_argument("--out", default=None, help="explicit scorecard output path override")
    args = ap.parse_args()

    gold_records = load_all_gold(GOLD_DIR)
    if args.pages:
        wanted = set(args.pages.split(","))
        gold_records = [g for g in gold_records if g.page_id in wanted]
        missing = wanted - {g.page_id for g in gold_records}
        if missing:
            print(f"WARNING: unknown page ids requested: {sorted(missing)}", file=sys.stderr)

    if not gold_records:
        print("No gold records selected; nothing to do.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading engine: {args.engine} ...")
    extractor = get_extractor(args.engine)

    restore_dir = tempfile.mkdtemp(prefix="blast_eval_restore_")
    per_page = []
    try:
        for gold in gold_records:
            image_path = PAGES_DIR / f"{gold.page_id}.png"
            if not image_path.exists():
                print(f"WARNING: missing source image for {gold.page_id}: {image_path}", file=sys.stderr)
                continue
            print(f"  scoring {gold.page_id} ...", end=" ", flush=True)
            page_result = run_one_page(extractor, gold, image_path, restore_dir)
            per_page.append(page_result)
            tau = page_result["reading_order_tau"]
            tau_disp = f"{tau:.3f}" if tau is not None else "n/a"
            print(
                f"CER={page_result['cer']:.4f} WER={page_result['wer']:.4f} "
                f"tau={tau_disp} facts={page_result['fact_pass_count']}/{page_result['fact_total_count']} "
                f"({page_result['elapsed_sec']}s)"
            )
    finally:
        shutil.rmtree(restore_dir, ignore_errors=True)

    scorecard = {
        "schema_version": SCHEMA_VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
        "engine": args.engine,
        "aggregate": build_aggregate(per_page),
        "per_page": per_page,
    }

    print_report(scorecard)

    if not args.no_save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = Path(args.out) if args.out else RESULTS_DIR / f"{scorecard['git_sha']}.json"
        out_path.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
        print(f"\nScorecard written to {out_path}")

    return scorecard


if __name__ == "__main__":
    main()
