"""
Root GUI Entry Point
"""
import sys
import os

# Add root to path so blast_ocr can be imported
sys.path.append(os.path.dirname(__file__))

import os

if __name__ == "__main__":
    print("Launching Streamlit Dashboard...")
    # Streamlit runs as a separate process
    os.system("streamlit run blast_ocr/ui/web_app.py")
