import os
import sys
import json
import argparse
from typing import Dict, Callable

# New Pipeline Import
from blast_ocr.pipeline import BlastPipeline

# Wrapper for existing CLI/API compatibility
def main(source_path, output_dir=None, progress_callback: Callable = None, config: Dict = None):
    pipeline = BlastPipeline(config_overrides=config)
    return pipeline.process_job(source_path, output_dir, progress_callback)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Path to file")
    parser.add_argument("--out", help="Output directory")
    args = parser.parse_args()
    
    print(json.dumps(main(args.source, args.out), indent=2))
