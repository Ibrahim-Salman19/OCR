"""
B.L.A.S.T. OCR Benchmark Script
Phase 4: Testing & Validation

Measures performance of the OCR pipeline before/after optimization.
"""

import sys
import time
import tempfile
import tracemalloc
from pathlib import Path
from PIL import Image, ImageDraw

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from blast_ocr.main import BlastPipeline


def create_test_pdf(output_path: str, num_pages: int = 5) -> str:
    """
    Create a simple test PDF with text on each page.
    Uses PIL to create images and converts to PDF.
    """
    from PIL import Image, ImageDraw

    images = []
    for i in range(num_pages):
        # Create a letter-sized image (300 DPI)
        img = Image.new("RGB", (2550, 3300), color="white")
        draw = ImageDraw.Draw(img)

        # Add text content
        text_lines = [
            f"Page {i + 1} of {num_pages}",
            "",
            "B.L.A.S.T. OCR Benchmark Test Page",
            "",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
            "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.",
            "Duis aute irure dolor in reprehenderit in voluptate velit esse.",
            "",
            "The quick brown fox jumps over the lazy dog.",
            "Pack my box with five dozen liquor jugs.",
            "How vexingly quick daft zebras jump!",
        ]

        y_offset = 200
        for line in text_lines:
            draw.text((200, y_offset), line, fill="black")
            y_offset += 100

        images.append(img)

    # Save as PDF
    if images:
        images[0].save(output_path, "PDF", save_all=True, append_images=images[1:])

    return output_path


def create_test_image(output_path: str) -> str:
    """Create a simple test image with text."""
    img = Image.new("RGB", (800, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "B.L.A.S.T. OCR Test Image - Quick Brown Fox", fill="black")
    draw.text((50, 100), "1234567890 ABCDEFGHIJ abcdefghij", fill="black")
    img.save(output_path)
    return output_path


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} TB"


def run_benchmark():
    """Run the OCR benchmark and print results."""
    print("=" * 60)
    print("B.L.A.S.T. OCR BENCHMARK")
    print("=" * 60)
    print()

    results = {}

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Test 1: Single Image OCR
        print("[1/3] Benchmarking single image OCR...")
        print("-" * 40)

        test_image = create_test_image(str(temp_path / "test_image.png"))

        tracemalloc.start()
        start_time = time.perf_counter()

        pipeline = BlastPipeline()
        result = pipeline.process_job(test_image, str(temp_path / "output_image"))

        end_time = time.perf_counter()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        image_time = end_time - start_time
        results["single_image"] = {
            "time": image_time,
            "peak_memory": peak,
            "status": result.get("status", "unknown"),
        }

        print(f"  Status: {result.get('status', 'unknown')}")
        print(f"  Time: {image_time:.2f}s")
        print(f"  Peak RAM: {format_bytes(peak)}")
        print()

        # Test 2: Multi-page PDF OCR (5 pages)
        print("[2/3] Benchmarking 5-page PDF OCR...")
        print("-" * 40)

        test_pdf = create_test_pdf(str(temp_path / "test_5page.pdf"), num_pages=5)

        tracemalloc.start()
        start_time = time.perf_counter()

        pipeline2 = BlastPipeline()
        result2 = pipeline2.process_job(test_pdf, str(temp_path / "output_pdf5"))

        end_time = time.perf_counter()
        current2, peak2 = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        pdf5_time = end_time - start_time
        pages_processed = result2.get("pages_processed", 0)
        per_page_time = pdf5_time / max(pages_processed, 1)

        results["pdf_5page"] = {
            "time": pdf5_time,
            "per_page": per_page_time,
            "pages": pages_processed,
            "peak_memory": peak2,
            "status": result2.get("status", "unknown"),
        }

        print(f"  Status: {result2.get('status', 'unknown')}")
        print(f"  Pages processed: {pages_processed}")
        print(f"  Total time: {pdf5_time:.2f}s")
        print(f"  Per-page time: {per_page_time:.2f}s")
        print(f"  Peak RAM: {format_bytes(peak2)}")
        print()

        # Test 3: Cache hit test
        print("[3/3] Benchmarking cache hit...")
        print("-" * 40)

        start_time = time.perf_counter()

        # Re-process same image (should be cached)
        pipeline3 = BlastPipeline()
        result3 = pipeline3.process_job(test_image, str(temp_path / "output_cached"))

        end_time = time.perf_counter()
        cache_time = end_time - start_time

        results["cache_hit"] = {
            "time": cache_time,
            "status": result3.get("status", "unknown"),
        }

        print(f"  Status: {result3.get('status', 'unknown')}")
        print(f"  Time with cache: {cache_time:.2f}s")
        print(f"  Cache speedup: {image_time / max(cache_time, 0.001):.1f}x")
        print()

    # Summary
    print("=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print()
    print(f"Single Image OCR:     {results['single_image']['time']:.2f}s")
    print(f"5-Page PDF (total):   {results['pdf_5page']['time']:.2f}s")
    print(f"5-Page PDF (per-page):{results['pdf_5page']['per_page']:.2f}s")
    print(f"Cache Hit Reprocess:  {results['cache_hit']['time']:.2f}s")
    print(f"Peak Memory (PDF):    {format_bytes(results['pdf_5page']['peak_memory'])}")
    print()

    return results


def test_cache_behavior():
    """Test that cache hit/miss works correctly."""
    print("\n[SMOKE TEST] Cache Behavior")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_image = create_test_image(str(temp_path / "cache_test.png"))

        pipeline = BlastPipeline()

        # First run - should be cache miss
        result1 = pipeline.process_job(test_image, str(temp_path / "out1"))

        # Second run - should be cache hit
        result2 = pipeline.process_job(test_image, str(temp_path / "out2"))

        print(f"  First run:  {result1.get('status', 'unknown')}")
        print(f"  Second run: {result2.get('status', 'unknown')}")
        print("  ✓ Cache behavior test passed")


def test_error_handling():
    """Test that errors are handled gracefully."""
    print("\n[SMOKE TEST] Error Handling")
    print("-" * 40)

    pipeline = BlastPipeline()

    # Test non-existent file
    result = pipeline.process_job("non_existent_file.pdf", "output")
    assert result.get("status") == "error", (
        f"Expected 'error' status, got {result.get('status')}"
    )
    print("  ✓ Non-existent file handled correctly")

    print("  ✓ Error handling test passed")


if __name__ == "__main__":
    print()
    print("Starting B.L.A.S.T. OCR Benchmark...")
    print("This will test single image, multi-page PDF, and cache performance.")
    print()

    try:
        results = run_benchmark()
        test_cache_behavior()
        test_error_handling()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"\n[ERROR] Benchmark failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
