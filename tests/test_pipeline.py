from blast_ocr.main import main


def test_end_to_end_image(temp_workspace, sample_image):
    """Test full flow for single image"""
    # FIX(phase2): CRITICAL-003 - Removed references to non-existent module globals
    # (_db, _extractor, _logger, _parallel_processor, get_components).
    # These globals don't exist in main.py. The correct approach is to create
    # a fresh BlastPipeline which handles its own component initialization.

    print("\n--- DEBUG INFO ---")
    print(f"Test Workspace DB: {temp_workspace['db']}")
    print("------------------\n")

    print(f"Processing image: {sample_image}")

    # FIX(phase2): Use the main() function directly, which creates its own pipeline
    result = main(source_path=sample_image, output_dir=str(temp_workspace["output"]))

    print(f"Result: {result}")

    assert result["status"] == "success"
    assert result["pages_processed"] == 1

    # Check Output File
    out_files = list(temp_workspace["output"].glob("*.md"))
    assert len(out_files) == 1
    content = out_files[0].read_text(encoding="utf-8")
    assert isinstance(content, str)
