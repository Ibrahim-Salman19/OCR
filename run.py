"""
Root Entry Point
"""
import sys
import os

# Add root to path so blast_ocr can be imported
sys.path.append(os.path.dirname(__file__))

from blast_ocr.main import main
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="B.L.A.S.T. OCR Launcher")
    parser.add_argument("source", help="Source file or folder")
    parser.add_argument("--out", help="Output directory", default=None)
    args = parser.parse_args()
    
    main(args.source, args.out)
