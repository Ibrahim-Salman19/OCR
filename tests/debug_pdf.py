import sys
from pathlib import Path
import os
import logging

# Add project root
sys.path.append(str(Path(__file__).parent.parent))

from blast_ocr.main import get_components
from blast_ocr.config import config

# Enable Debug Logging
logging.basicConfig(level=logging.DEBUG)
logger, _, _, parallel_processor = get_components()
logger.setLevel(logging.DEBUG)


def debug_pdf(pdf_path):
    print(f"[-] Debugging PDF: {pdf_path}")

    if not os.path.exists(pdf_path):
        print("[!] File not found!")
        return

    # 1. Test Poppler Path from Config
    print(f"    Poppler Path: {config.poppler_path}")

    # 2. Run Process (Just first few pages if we could limit,
    # but process_pdf processes all. We'll trust the logger to show us what's happening)
    # Actually, let's override the parallel processor to be simpler/verbose or just run generic process_pdf

    try:
        # Optimization: convert_from_path supports first_page and last_page
        # We need to hack this into process_pdf or just use the logic from main.py here manually

        # Let's recreate the logic of process_pdf here but with limits
        from pdf2image import convert_from_path
        import tempfile
        from blast_ocr.main import process_single_image

        print("[-] Manually processing first 5 pages...")
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                kwargs = {}
                if config.poppler_path:
                    kwargs["poppler_path"] = config.poppler_path

                print("    Converting PDF (Limit 5 pages)...")
                pages = convert_from_path(
                    pdf_path, dpi=300, first_page=1, last_page=5, **kwargs
                )
                print(f"    Converted {len(pages)} pages.")
            except Exception as e:
                print(f"[!] PDF Conversion Failed: {e}")
                return

            results = []
            for i, page in enumerate(pages, 1):
                fname = f"page_{i:04d}.png"
                fpath = os.path.join(temp_dir, fname)
                page.save(fpath, "PNG")

                print(f"    OCR Page {i}...")
                res = process_single_image(fpath, i)
                results.append(res)

                text_preview = str(res.get("text", ""))[:50].replace("\n", " ")
                conf = res.get("confidence", 0)
                # Handle possible list/tuple confidence return if logic changed, but usually float
                if isinstance(conf, (list, tuple)):
                    conf = conf[0]

                print(f"    Page {i}: Conf={float(conf):.2f}, Text='{text_preview}...'")

        print("[-] Debug complete.")

    except Exception as e:
        print(f"[!] Crash: {e}")


if __name__ == "__main__":
    # Use the file provided by the user
    target_file = r"c:\Users\hafiz\OneDrive - University of Engineering and Technology Taxila\Desktop\Ibrahim\Projects\Python\OCR_Book\the-ideology-of-pakistan-javid-iqbal.pdf"
    debug_pdf(target_file)
