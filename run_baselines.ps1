$ErrorActionPreference = "Continue"
New-Item -ItemType Directory -Force -Path .tmp | Out-Null

echo "=== Line Counts ==="
Get-ChildItem -Path blast_ocr -Filter *.py -Recurse | ForEach-Object {
    $lines = (Get-Content $_.FullName | Measure-Object -Line).Lines
    [PSCustomObject]@{ File = $_.Name; Lines = $lines }
} | Sort-Object -Property Lines -Descending | Format-Table -AutoSize

echo "=== Syntax Check ==="
Get-ChildItem -Path blast_ocr -Filter *.py -Recurse | ForEach-Object { python -m py_compile $_.FullName }
echo "Syntax OK"

echo "=== Import Check ==="
python -c "import blast_ocr; print('Import OK')"

echo "=== Baseline Tests ==="
pytest tests/ -v --tb=short 2>&1 | Tee-Object -FilePath .tmp/baseline_results.txt

echo "=== Baseline Coverage ==="
pytest tests/ --cov=blast_ocr --cov-branch --cov-report=term-missing --cov-report=html:coverage_html 2>&1 | Tee-Object -FilePath .tmp/baseline_coverage.txt

echo "=== Mypy Static Analysis ==="
python -m mypy blast_ocr/ --ignore-missing-imports 2>&1 | Tee-Object -FilePath .tmp/mypy_results.txt

echo "=== Bandit Security Scan ==="
python -m bandit -r blast_ocr/ -ll 2>&1 | Tee-Object -FilePath .tmp/bandit_results.txt

echo "=== Safety Check ==="
python -m safety check 2>&1 | Tee-Object -FilePath .tmp/safety_results.txt

echo "DONE"
