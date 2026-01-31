import os
import sys
import json
import argparse
import datetime
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict

# Core imports
from blast_ocr.config import config
from blast_ocr.logging_config import setup_logging
from blast_ocr.storage.database import OCRDatabase
from blast_ocr.core.extractor import RobustOCRExtractor
from blast_ocr.core.parallel import ParallelOCRProcessor
from blast_ocr.cache.manager import cache_manager
from blast_ocr.core.text_extractor import extract_from_pptx, save_output  # Legacy for PPTX

# PDF support
from pdf2image import convert_from_path

# Global components (Lazy initialized)
_logger = None
_db = None
_extractor = None
_parallel_processor = None

def get_components():
    """Helper to get or initialize components (ensures env vars are picked up)"""
    global _logger, _db, _extractor, _parallel_processor
    if _logger is None:
        from blast_ocr.logging_config import setup_logging
        _logger = setup_logging(config.log_dir)
    if _db is None:
        _db = OCRDatabase()
    if _extractor is None:
        _extractor = RobustOCRExtractor()
    if _parallel_processor is None:
        _parallel_processor = ParallelOCRProcessor()
    return _logger, _db, _extractor, _parallel_processor

def process_single_image(image_path: str, page_num: int) -> Dict:
    """Worker function for single image processing"""
    logger, db, extractor, _ = get_components()
    # 1. Check Cache
    cached = cache_manager.get_cached_result(image_path)
    if cached:
        logger.info(f"Page {page_num}: Cache hit")
        return cached

    # 2. Extract
    try:
        result = extractor.process_page(image_path, page_num)
        
        # 3. Cache & DB
        cache_manager.save_to_cache(image_path, result)
        
        # We can't easily write to DB from worker threads if using SQLite (concurrency issues)
        # So we return result and write to DB in main thread or use queue
        return result
    except Exception as e:
        logger.error(f"Page {page_num} failed: {e}")
        return {"page": page_num, "text": "", "error": str(e), "confidence": 0.0}

def process_pdf(pdf_path: str, output_dir: str) -> List[Dict]:
    """Convert PDF to images and process in parallel"""
    logger, _, _, parallel_processor = get_components()
    logger.info(f"Converting PDF: {pdf_path}")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Convert PDF to images
        try:
            pages = convert_from_path(pdf_path, dpi=300, output_folder=temp_dir)
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            return []
        
        # Collect image paths
        # pdf2image saves with random names or we iterate the PIL objects.
        # But convert_from_path(output_folder=...) saves files.
        # Actually convert_from_path returns PIL images, dealing with files explicitly is better for parallel.
        # Let's save explicitly.
        image_paths = []
        for i, page in enumerate(pages, 1):
            fname = f"page_{i:04d}.png"
            fpath = os.path.join(temp_dir, fname)
            page.save(fpath, "PNG")
            image_paths.append(fpath)
            
        logger.info(f"Generated {len(image_paths)} page images. Starting OCR...")
        
        # Run Parallel OCR
        # We pass the function reference. The processor handles the threading/execution.
        results = parallel_processor.process_batch_threaded(image_paths, process_single_image)
        
        return results

def main(source_path, output_dir=None):
    logger, db, _, _ = get_components()
    if not os.path.exists(source_path):
        return {"status": "error", "message": f"Source not found: {source_path}"}
    
    if output_dir is None:
        output_dir = os.path.dirname(source_path) if os.path.isfile(source_path) else source_path
        
    os.makedirs(output_dir, exist_ok=True)
    
    # Analyze Source
    results = []
    source = Path(source_path)
    job_id = None
    
    if source.is_file():
        ext = source.suffix.lower()
        base_name = source.stem
        
        # Register Job
        job_id = db.create_job(source.name, page_count=0) # Update count later
        db.update_job_status(job_id, 'processing')
        
        try:
            if ext == '.pdf':
                results = process_pdf(str(source), output_dir)
            elif ext == '.pptx':
                # Legacy path for now
                text = extract_from_pptx(str(source))
                results = [{"page": 1, "text": text, "confidence": 1.0}] 
            elif ext in ['.png', '.jpg', '.jpeg']:
                results = [process_single_image(str(source), 1)]
            else:
                logger.warning(f"Unsupported extension: {ext}")
            
            # Aggregate Text
            full_text = "\n\n---\n\n".join([r.get('text', '') for r in results])
            
            # Save Output
            save_output(full_text, base_name, output_dir)
            
            # Update DB (Batch insert would be better but simple loop for now)
            start_time = datetime.datetime.utcnow() # Approximation
            for r in results:
                db.save_result(
                    job_id=job_id,
                    page_number=r.get('page', 0),
                    text=r.get('text', ''),
                    confidence=r.get('confidence', 0.0),
                    processing_time=0.0
                )
            
            db.update_job_status(job_id, 'completed')
            
        except Exception as e:
            logger.error(f"Job failed: {e}")
            db.update_job_status(job_id, 'failed', error_message=str(e))
            return {"status": "failed", "error": str(e)}

    return {
        "status": "success",
        "job_id": job_id,
        "pages_processed": len(results)
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Path to file")
    parser.add_argument("--out", help="Output directory")
    args = parser.parse_args()
    
    print(json.dumps(main(args.source, args.out), indent=2))
