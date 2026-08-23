"""Phase 0 regression gate: fails if OCR quality regresses vs. the committed
baseline scorecard.

This intentionally does NOT invoke the OCR pipeline itself -- doing so here
would make the entire (otherwise-fast, network-free) `pytest tests/` suite
slow and dependent on model downloads. Instead this test reads whatever
scorecard `python eval/run.py` most recently wrote to eval/results/ and
compares it against eval/results/baseline.json. Workflow:

    python eval/run.py                     # produces eval/results/<sha>.json
    pytest tests/test_eval_regression.py   # checks it against the baseline

To intentionally move the baseline forward after a verified improvement:
    cp eval/results/<new-sha>.json eval/results/baseline.json

Marked `eval_regression` (registered in pytest.ini) so it's collected by the
default `pytest tests/` run but SKIPS cleanly -- never fails -- when no
fresh full-corpus scorecard is present, e.g. on a machine that hasn't run
the harness yet.
"""

import json
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "eval" / "results"
BASELINE_PATH = RESULTS_DIR / "baseline.json"

# Absolute-value tolerances. CER/WER are computed from a real OCR engine
# run on real scans; tiny nondeterminism (thread scheduling affecting
# floating-point accumulation order) is possible even on CPU, so a zero
# tolerance would make this gate flaky. Fact-pass-rate is a discrete
# pass/fail count and is required not to regress at all.
CER_TOLERANCE = 0.005
WER_TOLERANCE = 0.01

pytestmark = pytest.mark.eval_regression


def _latest_scorecard() -> Optional[Path]:
    if not BASELINE_PATH.exists():
        return None
    base_mtime = BASELINE_PATH.stat().st_mtime
    candidates = []
    for p in RESULTS_DIR.glob("*.json"):
        if p.name == "baseline.json" or p.name.endswith("_report.json") or p.name.endswith("_scorecard.json"):
            continue
        # Skip static historical exploration candidate files
        if "candidate" in p.name:
            continue
        try:
            if p.stat().st_mtime <= base_mtime:
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "aggregate" in data:
                candidates.append(p)
        except Exception:
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def test_no_quality_regression_vs_baseline():
    if not BASELINE_PATH.exists():
        pytest.skip(
            f"No baseline scorecard at {BASELINE_PATH} yet -- nothing to "
            f"compare against. Run `python eval/run.py`, review the "
            f"result, then commit it as eval/results/baseline.json."
        )

    latest_path = _latest_scorecard()
    if latest_path is None:
        pytest.skip(
            "No scorecard found in eval/results/. Run `python eval/run.py` "
            "first, then re-run this test."
        )

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    latest = json.loads(latest_path.read_text(encoding="utf-8"))

    base_agg = baseline["aggregate"]
    new_agg = latest["aggregate"]

    if new_agg["page_count"] != base_agg["page_count"]:
        pytest.skip(
            f"Latest scorecard ({latest_path.name}) covers "
            f"{new_agg['page_count']} pages but the baseline covers "
            f"{base_agg['page_count']} -- looks like a partial `--pages` "
            f"run, not a full-corpus run. Re-run `python eval/run.py` "
            f"without --pages to check for regressions."
        )

    failures = []

    if new_agg["mean_cer"] > base_agg["mean_cer"] + CER_TOLERANCE:
        failures.append(
            f"mean CER regressed: {base_agg['mean_cer']:.4f} -> "
            f"{new_agg['mean_cer']:.4f} (tolerance {CER_TOLERANCE})"
        )

    if new_agg["mean_wer"] > base_agg["mean_wer"] + WER_TOLERANCE:
        failures.append(
            f"mean WER regressed: {base_agg['mean_wer']:.4f} -> "
            f"{new_agg['mean_wer']:.4f} (tolerance {WER_TOLERANCE})"
        )

    base_fact_rate = base_agg.get("fact_pass_rate")
    new_fact_rate = new_agg.get("fact_pass_rate")
    if base_fact_rate is not None and new_fact_rate is not None:
        if new_fact_rate < base_fact_rate:
            failures.append(
                f"fact-check pass rate regressed: "
                f"{base_fact_rate * 100:.1f}% -> {new_fact_rate * 100:.1f}% "
                f"({new_agg['fact_pass_count']}/{new_agg['fact_total_count']} "
                f"vs {base_agg['fact_pass_count']}/{base_agg['fact_total_count']})"
            )

    assert not failures, (
        f"OCR quality regressed vs baseline ({latest_path.name} vs "
        f"baseline.json, baseline sha={baseline.get('git_sha')}):\n"
        + "\n".join(f"  - {f}" for f in failures)
    )
