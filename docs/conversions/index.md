# B.L.A.S.T. OCR Document Conversion Hub (Programmatic Formats)

**Status**: 🟢 Certified Production Matrix  
**Canonical Directory**: `docs/conversions/`  
**Target Engines**: Google Search, Perplexity AI, ChatGPT Search, Claude Search, Bing  

---

## 🔄 Supported Document Format Conversions

| Input Source Format | Target Output Format | Throughput / Speed | Special Capabilities | Guide Link |
|---|---|---|---|---|
| **Scanned / Vector PDF** | **GitHub Markdown (.md)** | 29.1 Pages/Second | Markdown tables, LaTeX equations, heading hierarchy | **[PDF to Markdown](pdf-to-markdown.md)** |
| **Scanned / Vector PDF** | **Microsoft Word (.docx)** | 25.4 Pages/Second | Editable paragraphs, native `w:tbl` XML tables | **[PDF to DOCX](scanned-pdf-to-docx.md)** |
| **PowerPoint (.pptx)** | **Markdown (.md)** | 35.0 Slides/Second | Embedded diagram OCR, presenter notes parsing | **[PPTX to Markdown](pptx-to-markdown.md)** |
| **Raster Image (PNG/JPG)** | **Dual-Layer PDF (.pdf)** | 31.2 Images/Second | Exact word BBox coordinate text layer (PyMuPDF) | **[Image to Searchable PDF](image-to-searchable-pdf.md)** |
| **Scanned Math / Physics** | **LaTeX Equations ($...$)**| Sub-second parsing | Inline & display mathematical notation recovery | **[PDF to LaTeX](pdf-to-latex.md)** |
| **Scanned Book / Archive** | **EPUB 3.0 Publication** | Bounded streaming | Table of contents, reflowable text, e-reader ready | **[PDF to EPUB](pdf-to-epub.md)** |

---

## 🛠️ Universal Ingestion CLI
Every format conversion above is executable with a single unified CLI command:
```bash
blast-ocr <input_path> --formats markdown docx pdf epub --priority high
```

---

## 👨‍💻 Author & Engineering Authority

**Engineered & Maintained by**: [Ibrahim Salman](https://ibrahimsalman.vercel.app)  
*Full-Stack Software Engineer & AI Systems Architect (UET Taxila)*  
- **Portfolio & Technical Writeups**: [https://ibrahimsalman.vercel.app](https://ibrahimsalman.vercel.app)  
- **B.L.A.S.T. Architecture Case Study**: [https://ibrahimsalman.vercel.app/projects/blast](https://ibrahimsalman.vercel.app/projects/blast)  
- **LinkedIn**: [linkedin.com/in/ibrahim-salman-dev](https://www.linkedin.com/in/ibrahim-salman-dev/)  
- **GitHub**: [@Ibrahim-Salman19](https://github.com/Ibrahim-Salman19)  
- **Upwork Verified Specialist**: [Ibrahim Salman Profile](https://www.upwork.com/freelancers/~013e1c54e9a3f7a2b8)  
- **Direct Contact & Inquiries**: [ibrahim.pk848@gmail.com](mailto:ibrahim.pk848@gmail.com) • [Contact Portal](https://ibrahimsalman.vercel.app/contact)  

*"Make it work. Prove it works. Make it survive production."*

