"""
B.L.A.S.T. Interface
Phase: Stylize (GUI)

A Streamlit dashboard for the OCR automation.
"""
import streamlit as st
import os
import shutil
import time
from pathlib import Path
import os
import shutil
import time
from pathlib import Path
import sys

from blast_ocr.core.text_extractor import extract_from_pptx, extract_from_pdf, extract_from_image, save_output

st.set_page_config(page_title="B.L.A.S.T. OCR", page_icon="🚀", layout="centered")

def process_file(uploaded_file, output_dir):
    # Save temp
    bytes_data = uploaded_file.getvalue()
    temp_path = os.path.join(".tmp", uploaded_file.name)
    os.makedirs(".tmp", exist_ok=True)
    with open(temp_path, "wb") as f:
        f.write(bytes_data)
        
    base_name = os.path.splitext(uploaded_file.name)[0]
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    
    text = None
    status_text = st.empty()
    status_text.info(f"Processing {uploaded_file.name}...")
    
    try:
        if ext == ".pptx":
            text = extract_from_pptx(temp_path)
        elif ext == ".pdf":
            text = extract_from_pdf(temp_path)
        elif ext in ['.png', '.jpg', '.jpeg', '.bmp']:
            text = extract_from_image(temp_path)
        else:
            st.error(f"Unsupported format: {ext}")
            return None, None

        if text:
            md, docx = save_output(text, base_name, output_dir)
            status_text.success(f"Done: {base_name}")
            return md, docx
    except Exception as e:
        st.error(f"Error: {e}")
        return None, None
    finally:
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

# --- UI ---
st.title("🚀 B.L.A.S.T. OCR Engine")
st.markdown("### Deterministic Text Extraction")

# File Uploader
uploaded_files = st.file_uploader("Drop your files here (PDF, PPTX, Images)", 
                                  accept_multiple_files=True,
                                  type=['pptx', 'pdf', 'png', 'jpg', 'jpeg'])

if uploaded_files:
    if st.button(f"Process {len(uploaded_files)} Files"):
        progress_bar = st.progress(0)
        output_dir = "gui_output"
        os.makedirs(output_dir, exist_ok=True)
        
        results = []
        for i, f in enumerate(uploaded_files):
            md, docx = process_file(f, output_dir)
            if md:
                results.append(md)
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        st.balloons()
        st.success(f"Processed {len(results)} files successfully!")
        st.write(f"Outputs saved to `{os.path.abspath(output_dir)}`")
        
        # Zip download
        shutil.make_archive("blast_output", 'zip', output_dir)
        with open("blast_output.zip", "rb") as fp:
            st.download_button(
                label="📦 Download All Results (ZIP)",
                data=fp,
                file_name="blast_output.zip",
                mime="application/zip"
            )

st.sidebar.markdown("### Status")
st.sidebar.info("System Ready")
st.sidebar.markdown("---")
st.sidebar.text("B.L.A.S.T. Protocol v1.0")
