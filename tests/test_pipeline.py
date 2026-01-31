import pytest
import os
from blast_ocr.main import main
from blast_ocr.storage.database import OCRDatabase, OCRJob

def test_end_to_end_image(temp_workspace, sample_image):
    """Test full flow for single image"""
    from blast_ocr.config import config
    import blast_ocr.main as bmain

    # Force reload of config settings from environment
    config.__init__(_env_file=config.model_config.get('env_file'))
    # Reset globals in main to pick up mocked env vars
    bmain._db = None
    bmain._extractor = None
    bmain._logger = None
    bmain._parallel_processor = None
    
    logger, db, _, _ = bmain.get_components()
    
    print(f"\n--- DEBUG INFO ---")
    print(f"Config DB URL: {config.database_url}")
    print(f"Main DB Path: {db.db_url}")
    print(f"Test Workspace DB: {temp_workspace['db']}")
    print(f"------------------\n")
    
    print(f"Processing image: {sample_image}")
    result = main(
        source_path=sample_image,
        output_dir=str(temp_workspace['output'])
    )
    
    print(f"Result: {result}")
    
    assert result['status'] == 'success'
    assert result['pages_processed'] == 1
    
    # Check DB
    # Re-use the db path from main's initialized db to be extra sure
    db_results = OCRDatabase(db_path=db.db_url)
    jobs = db_results.session.query(OCRJob).all()
    assert len(jobs) == 1
    assert jobs[0].status == 'completed'
    
    # Check Output File
    out_files = list(temp_workspace['output'].glob("*.md"))
    assert len(out_files) == 1
    content = out_files[0].read_text(encoding='utf-8')
    assert len(content) > 0
