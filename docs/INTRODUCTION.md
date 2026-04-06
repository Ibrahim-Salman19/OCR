# 🚀 Introduction to B.L.A.S.T. OCR

**Blueprint. Link. Architect. Stylize. Trigger.**

B.L.A.S.T. is not just an OCR script; it is a **Deterministic Automation Agent** designed for high-stakes document processing. In an era where "mostly correct" is not enough, B.L.A.S.T. provides a rigorous, self-healing pipeline that transforms raw PDFs, PowerPoints, and Images into structured, production-ready Markdown and DOCX artifacts.

## 🎯 The Vision

The core vision of B.L.A.S.T. is to bridge the gap between volatile OCR engines (like EasyOCR/Tesseract) and enterprise-grade reliability. We achieve this through:

1.  **Forensic Stability**: Solving the "voodoo" of memory leaks and race conditions through strict architectural patterns.
2.  **Self-Healing**: A tiered retry system that distinguishes between transient engine glitches and fatal file corruption.
3.  **Security-First Design**: Native protection against XXE, SQLi, and cross-user data bleeding.

## 👥 User Personas

-   **Data Scientists**: Automate the creation of large-scale text datasets from legacy PDF archives.
-   **Legal & Finance**: Extract high-fidelity text from scanned contracts with audit trails and confidence scores.
-   **Developers**: Integrate a robust OCR backend into existing web applications via the headless API or the Streamlit dashboard.

## 🛠️ Core Capabilities

| Format | Library | Capability |
| :--- | :--- | :--- |
| **PDF** | `pdf2image` (Poppler) | Multi-page splitting with high-DPI rendering via `pdftocairo`. |
| **PPTX** | `python-pptx` | Table extraction, slide text mapping, and forensic XML cleaning. |
| **Images** | `OpenCV` / `PIL` | Grayscale normalization, CLAHE enhancement, and noise reduction. |
| **OCR** | `EasyOCR` | Deep-learning based text recognition with 80+ language support. |

## 🔗 Next Steps
-   [Architecture Deep Dive](ARCHITECTURE_DEEP_DIVE.md)
-   [Security Hardening Guide](SECURITY_HARDENING.md)
-   [Installation & Deployment](DEPLOYMENT_GUIDE.md)
-   [OCR Engine Evaluation (2026)](OCR_ENGINE_EVALUATION_2026.md)
