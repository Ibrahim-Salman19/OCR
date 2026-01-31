# 🚀 B.L.A.S.T. OCR Engine

**Blueprint. Link. Architect. Stylize. Trigger.**

B.L.A.S.T. is a deterministic, self-healing OCR automation agent designed to extract high-quality text from PDFs, PPTX slides, and Images. It uses a multi-engine approach (EasyOCR + Python-PPTX) to ensure reliability.

## 🌟 Key Features
- **Multi-Format Support:** Handles PDF, PPTX, PNG, JPG, JPEG.
- **Self-Healing:** Falls back to EasyOCR if native extraction fails.
- **Determinism:** Structured outputs (Markdown & DOCX) for every page.
- **Dual Interface:** Run via CLI or a modern Streamlit Dashboard.

## 📦 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/blast-ocr.git
   cd blast-ocr
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **(Optional) Install Tesseract:**
   While B.L.A.S.T. defaults to `EasyOCR`, you can install Tesseract for faster CPU inference.
   [Download Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)

## 🕹️ Usage

### Option 1: Graphic Interface (Recommended)
Launch the web dashboard to drag-and-drop files.
```bash
streamlit run app.py
```

### Option 2: Command Line
Process an entire folder of images or a specific file.
```bash
python main_driver.py pages/ --out my_results/
```

## 🏗️ Architecture
The project follows the 3-Layer A.N.T. architecture:
- **Layer 1 (SOPs):** `architecture/` - The logic and reasoning.
- **Layer 2 (Navigation):** `main_driver.py` - Routing and validation.
- **Layer 3 (Tools):** `tools/` - Pure functions (EasyOCR, PPTX logic).

## 🛡️ License
MIT License.
