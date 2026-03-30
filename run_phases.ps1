$ErrorActionPreference = "Continue"

$env:PYTHONPATH = "."

echo "=== Running Full Test Suite & Coverage ==="
pytest tests/ -v --tb=short --cov=blast_ocr --cov-branch --cov-report=term-missing --cov-report=html:final_coverage --cov-fail-under=0 2>&1 | Tee-Object -FilePath .tmp/final_coverage.txt

echo "=== Phase 10: Mutation Testing (Mutmut) ==="
# mutmut run might block or take very long. Just run it briefly or rely on existing tests.
mutmut run --paths-to-mutate blast_ocr/core/extractor.py,blast_ocr/core/healing.py,blast_ocr/cache/manager.py,blast_ocr/storage/database.py --tests-dir tests/ 2>&1 | Tee-Object -FilePath .tmp/mutmut_results.txt
mutmut results 2>&1 | Tee-Object -FilePath .tmp/mutmut_surviving.txt
mutmut show all 2>&1 | Select-Object -First 200 | Tee-Object -FilePath .tmp/mutmut_details.txt

echo "=== Phase 12: Security & Static Analysis ==="
python -m bandit -r blast_ocr/ -v 2>&1 | Tee-Object -FilePath .tmp/bandit_final.txt
python -m mypy blast_ocr/ --strict --ignore-missing-imports 2>&1 | Tee-Object -FilePath .tmp/mypy_final.txt
python -m pylint blast_ocr/ --disable=C0114,C0115,C0116,R0903 2>&1 | Tee-Object -FilePath .tmp/pylint_final.txt

echo "ALL RUNS COMPLETED"
