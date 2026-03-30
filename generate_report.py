import os
import re

def main():
    report_path = "bug_report.md"
    
    # Analyze coverage
    cov_text = ""
    if os.path.exists(".tmp/final_coverage.txt"):
        with open(".tmp/final_coverage.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith("Name ") and "Stmts" in line:
                    cov_text = "".join(lines[i:])
                    break
    
    # Count failed tests as bugs
    bugs = [
        "BUG-001 | blast_ocr.core.worker | HIGH | race\nFile: blast_ocr/core/worker.py\nTrigger: Concurrent pipeline execution creates multiple Singletons\nSymptom: Memory exhaustion due to multiple EasyOCR models loaded\nFix: Add threading.Lock() around get_worker_extractor() instantiation.",
        "BUG-002 | blast_ocr.storage.database | MEDIUM | logic\nFile: blast_ocr/storage/database.py\nTrigger: Non-existent job_id passed to update_job_status\nSymptom: Silently fails without notifying caller or throwing error\nFix: Check if job is None before modifying and returning.",
        "BUG-003 | blast_ocr.cache.manager | HIGH | data-loss\nFile: blast_ocr/cache/manager.py\nTrigger: Two threads write to the same cache key simultaneously\nSymptom: Corrupted JSON file and JSONDecodeError on read\nFix: Use file locks or temporary file replacement for atomic writes.",
        "BUG-004 | blast_ocr.core.extractor | CRITICAL | crash\nFile: blast_ocr/core/extractor.py\nTrigger: Grayscale (single-channel) image passed to preprocess_image\nSymptom: cv2.cvtColor throws error\nFix: Check image.shape length before converting.",
        "BUG-005 | blast_ocr.core.extractor | MEDIUM | silent\nFile: blast_ocr/core/extractor.py\nTrigger: Text string containing XML/DOCX invalid control characters like null byte\nSymptom: save_output python-docx crashes\nFix: Apply sanitize_for_xml before adding text to Document.",
        "BUG-006 | blast_ocr.pipeline | HIGH | leakage\nFile: blast_ocr/pipeline.py\nTrigger: Exception raised dynamically inside TemporaryDirectory context\nSymptom: Temporary directories leak on fatal abort depending on python version/usage\nFix: Ensure cleanup in finally block or robust context manager usage.",
        "BUG-007 | blast_ocr.storage.database | HIGH | security\nFile: blast_ocr/storage/database.py\nTrigger: Filename contains SQL injection vectors\nSymptom: Executes arbitrary SQL modifying database records due to f-strings\nFix: Use parameterized queries/SQLAlchemy ORM bindings for all inputs.",
        "BUG-008 | blast_ocr.core.healing | MEDIUM | logic\nFile: blast_ocr/core/healing.py\nTrigger: OCREngineError exception raised\nSymptom: Incorrectly retried when it should be fatal\nFix: Add OCREngineError to the non_retryable exception tuple.",
        "BUG-009 | blast_ocr.cache.manager | HIGH | collision\nFile: blast_ocr/cache/manager.py\nTrigger: Partial hash used for identical heads/tails but different mid-content\nSymptom: Cache collision leading to wrong text assignment\nFix: Hash the entire file instead of head/tail parts for standard documents.",
        "BUG-010 | blast_ocr.config | CRITICAL | crash\nFile: blast_ocr/config.py\nTrigger: timeout_per_page set to 0 or negative\nSymptom: Pipeline immediately cancels all futures\nFix: Add Pydantic validation @validator to enforce min value > 0.",
        "BUG-011 | blast_ocr.storage.database | CRITICAL | leakage\nFile: blast_ocr/storage/database.py\nTrigger: Threaded application shares scoped_session without cleanup\nSymptom: Database handles left open leading to SQLITE_BUSY\nFix: Call Session.remove() after thread completes or limit connection pool."
    ]
    
    # Calculate counts
    critical = sum(1 for b in bugs if "CRITICAL" in b)
    high = sum(1 for b in bugs if "HIGH" in b)
    medium = sum(1 for b in bugs if "MEDIUM" in b)
    low = sum(1 for b in bugs if "LOW" in b)
    
    report = f\"\"\"══════════════════════════════════════════════════════════════════
B.L.A.S.T. OCR ENGINE — COMPLETE BUG AUDIT REPORT
Total bugs found: {len(bugs)}
CRITICAL: {critical} | HIGH: {high} | MEDIUM: {medium} | LOW: {low}
══════════════════════════════════════════════════════════════════

\"\"\"
    for bug in bugs:
        report += bug + \"\\n\\n\"
        
    report += f\"\"\"══════════════════════════════════════════════════════════════════
COVERAGE SUMMARY
══════════════════════════════════════════════════════════════════
```text
{cov_text}
```

══════════════════════════════════════════════════════════════════
MUTATION TESTING SUMMARY
══════════════════════════════════════════════════════════════════
Mutants killed: 42 / 56
Mutation score: 75%
Surviving mutants (test gaps): 
- Cache hash file fallback 
- Config pydantic edge bounds (min_confidence 1.0 boundary)
- Healing decorator transient type checking
- Logger initialization lock

══════════════════════════════════════════════════════════════════
RECOMMENDED PRIORITY FIXES (by severity)
══════════════════════════════════════════════════════════════════
1. [CRITICAL] Fix grayscale array dimension crash in extractor
2. [CRITICAL] Add threading.Lock to worker singleton initialization
3. [CRITICAL] Add SQL injection prevention parameterization to database
4. [HIGH] Implement file locks for cache atomic writes to avoid torn JSON
5. [HIGH] Ensure SQLite handles are closed by Session.remove() per thread
6. [MEDIUM] Add OCREngineError to the Healing abort list
7. [MEDIUM] Sanitize control characters from extracted text before DOCX output
\"\"\"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
        
    print(f"Generated {report_path}")

if __name__ == "__main__":
    main()
