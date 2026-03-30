import os
import glob
from datetime import datetime

def generate_md():
    out = []
    out.append("# B.L.A.S.T. OCR Engine - AI System Context")
    out.append(f"> Generated on: {datetime.now().strftime('%Y-%m-%d')} | Author: devhms | Branch: main\n")
    
    out.append("This document aggregates the entire B.L.A.S.T. OCR architecture, source code, tests, and skills into a single file. ")
    out.append("CRITICAL INSTRUCTION FOR AI AGENTS: Read this file carefully to understand the exact structure, constraints (A.N.T. architecture), and historical bug fixes (memory accumulation, CPU locking) before making ANY code changes.\n")

    def add_section(title, target_audience, description):
        out.append(f"## {title}")
        out.append(f"**🎯 Target Audience:** {target_audience}")
        out.append(f"*{description}*\n")

    def add_file(filepath, description=""):
        if os.path.exists(filepath):
            out.append(f"### 📄 File: `{filepath}`")
            if description:
                out.append(f"*{description}*\n")
            
            ext = os.path.splitext(filepath)[1].lower().replace('.', '')
            lang = ext if ext in ['py', 'css', 'html', 'js', 'json', 'toml', 'yaml', 'md', 'sh'] else 'text'
            if ext == '': lang = 'text'
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            out.append(f"```{lang}\n{content}\n```\n")
        else:
            out.append(f"> ⚠️ File not found: `{filepath}`\n")

    # Section 1
    add_section("1. Executive Summary", "AI Agent / Developer", "High-level overview of the project goal and outcomes.")
    out.append("The B.L.A.S.T. OCR Engine is a Deterministic OCR Automation tool designed for large-scale, automated extraction of text from scanned images, PDFs, and PPTX files. It implements a 3-layer A.N.T. architecture for stability, error recovery, and ultimate performance, prioritizing determinism over guesswork.\n")

    # Section 2
    add_section("2. Project Overviews & Entry Points", "AI Agent", "Core documentation and execution wrappers.")
    add_file("README.md", "Project Main Entry Documentation")
    add_file("gemini.md", "Project Master Plan & Source of Truth")
    add_file("ARCHITECTURE.md", "A.N.T. Design Philosophy")
    add_file("architecture/extraction_flow.md", "Pipeline Routing Logic")
    add_file("run.py", "CLI Application Entry Point")

    # Section 3
    add_section("3. Environment & Setup", "AI Agent", "Required configurations, dependencies, and health checks.")
    add_file("requirements.txt", "Python Dependencies")
    add_file("packages.txt", "System / OS Dependencies")
    add_file(".env.example", "Environment Variables Template")
    add_file("dll_check.py", "Windows Environment Integrity Check")
    add_file("verify_foundation.py", "System Health Verification Script")

    # Section 4
    add_section("4. Core Pipeline & Logic", "AI Agent", "The central orchestration engine and workers.")
    add_file("blast_ocr/main.py", "API/CLI wrapper for backend interactions.")
    add_file("blast_ocr/pipeline.py", "Orchestrates batching, processing, and output generation.")
    add_file("blast_ocr/core/extractor.py", "Implements CV2 preprocessing and EasyOCR execution.")
    add_file("blast_ocr/core/worker.py", "Worker thread allocation for single page extraction.")

    # Section 5
    add_section("5. Caching & Storage", "AI Agent", "Performance optimization and persistence.")
    add_file("blast_ocr/cache/manager.py", "Deduplication and processing bypass logic.")
    add_file("blast_ocr/storage/database.py", "SQLAlchemy ORM setup and ThreadLocal sessions.")

    # Section 6
    add_section("6. User Interface", "AI Agent", "Streamlit Dashboard components.")
    add_file("blast_ocr/ui/web_app.py", "Main Streamlit Dashboard Engine")
    add_file("blast_ocr/ui/styles.css", "Custom CSS Injection for Premium Glassmorphism Look")
    add_file(".streamlit/config.toml", "Streamlit Theming Engine")
    add_file("run_gui.py", "Streamlit Loader")

    # Section 7
    add_section("7. Resiliency & Configuration", "AI Agent", "Error handling, multi-threading, and app config.")
    add_file("blast_ocr/core/healing.py", "Retry loops and back-off architectures")
    add_file("blast_ocr/core/exceptions.py", "Custom Exceptions and Error Classifications")
    add_file("blast_ocr/core/parallel.py", "Manages multiple document workers securely")
    add_file("blast_ocr/config.py", "Pydantic Settings Models")
    add_file("blast_ocr/logging_config.py", "Structured JSON and Desktop Loging Strategies")

    # Section 8
    add_section("8. Quality Assurance & Tests", "AI Agent", "Unit tests ensuring core operations.")
    for tf in sorted(glob.glob("tests/*.py")):
        add_file(tf, "QA Suite Component")

    # Section 9
    add_section("9. Maintenance & Audits", "AI Agent", "Project maintenance utilities to track system erosion.")
    add_file("AUDIT.md", "Performance and Memory Leak Audit")
    add_file("maintain.py", "Cleanup and health check automations")
    add_file("inventory_gen.py", "Workspace context gathering utility")
    add_file("ENHANCEMENTS.md", "Visual and Logic upgrades")
    add_file("CHANGELOG.md", "Historical adjustments")
    add_file("CONTRIBUTING.md", "Rules of Engagement")
    add_file("DEVTOOLS_GUIDE.md", "Frontend Debugging Patterns")

    # Section 10
    add_section("10. Skill Knowledge Base", "AI Agent", "Distilled logic and patterns for maintaining the engine.")
    for sf in sorted(glob.glob("skills/*.md")):
        add_file(sf, "System Context Meta-Skill")

    # Section 11
    add_section("11. Benchmarking & Full Source Code Roster", "AI Agent", "Metrics scripts and repository maps.")
    add_file("benchmark.py", "Measures execution speeds and limits.")
    
    out.append("### 📄 Complete File System Roster")
    tree_str = ""
    for root, dirs, files in os.walk("."):
        if ".git" in root or "__pycache__" in root or ".pytest_cache" in root or "output" in root or "temp" in root: continue
        level = root.replace(".", "").count(os.sep)
        indent = " " * 4 * (level)
        tree_str += f"{indent}{os.path.basename(root)}/\n"
        subindent = " " * 4 * (level + 1)
        for f in files:
            tree_str += f"{subindent}{f}\n"

    out.append(f"```text\n{tree_str}\n```\n")

    # Write
    out_path = "AI_SYSTEM_CONTEXT.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"SUCCESS: AI Context Markdown generated at {out_path}")

if __name__ == "__main__":
    generate_md()
