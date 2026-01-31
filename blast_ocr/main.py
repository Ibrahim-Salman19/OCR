"""
Layer 2 Navigation: Main Driver
Phase: Architect

Entry point for the B.L.A.S.T. automation.
Routes inputs to the correct tools and manages the overall workflow.
"""

import os
import sys
import json
import argparse
import datetime
import os
import sys
import json
import argparse
import datetime
from pathlib import Path

from blast_ocr.core.text_extractor import extract_from_pptx, extract_from_pdf, extract_from_image, save_output

def main(source_path, output_dir=None):
    # 1. Validation
    if not os.path.exists(source_path):
        return {"status": "error", "message": f"Source not found: {source_path}"}
    
    if output_dir is None:
        if os.path.isfile(source_path):
            output_dir = os.path.dirname(source_path)
        else:
            output_dir = source_path
            
    # 2. Routing
    results = {}
    files_to_process = []
    
    if os.path.isfile(source_path):
        files_to_process.append(source_path)
    else:
        # Recursive walker if needed, or simple list
        for root, dirs, files in os.walk(source_path):
            for file in files:
                files_to_process.append(os.path.join(root, file))
                
    # 3. Processing
    processed_count = 0
    generated_files = []
    
    print(f"[-] Found {len(files_to_process)} candidates.")
    
    for fpath in files_to_process:
        ext = os.path.splitext(fpath)[1].lower()
        base_name = os.path.splitext(os.path.basename(fpath))[0]
        
        text_result = None
        
        try:
            if ext == ".pptx":
                print(f"[-] Extracting PPTX: {base_name}")
                text_result = extract_from_pptx(fpath)
            elif ext == ".pdf":
                print(f"[-] Extracting PDF: {base_name}")
                text_result = extract_from_pdf(fpath)
            elif ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
                print(f"[-] Extracting Image: {base_name}")
                text_result = extract_from_image(fpath)
            
            if text_result:
                # Save
                md, docx = save_output(text_result, base_name, output_dir)
                generated_files.append({"source": base_name, "md": md, "docx": docx})
                processed_count += 1
                
        except Exception as e:
            print(f"[!] Error processing {base_name}: {e}")
            
    # 4. Payload Generation
    payload = {
        "status": "success",
        "processed_count": processed_count,
        "timestamp": datetime.datetime.now().isoformat(),
        "generated_files": generated_files
    }
    
    return payload

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="B.L.A.S.T. Text Extraction Automation")
    parser.add_argument("source", help="Path to file or folder")
    parser.add_argument("--out", help="Output directory", default=None)
    
    args = parser.parse_args()
    
    result = main(args.source, args.out)
    print(json.dumps(result, indent=2))
