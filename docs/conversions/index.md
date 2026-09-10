# B.L.A.S.T. OCR Document Conversion Hub (Programmatic Formats)

**Status**: 🟡 Figures Checked Against Source, 2026-09-10  
**Canonical Directory**: `docs/conversions/`  
**Target Engines**: Google Search, Perplexity AI, ChatGPT Search, Claude Search, Bing  

---

## 🔄 Supported Document Format Conversions

The only throughput figure this project has actually measured is OCR latency on its 14-page gold corpus: ~15.3s/page ([`docs/BENCHMARKS_2026.md`](https://github.com/Ibrahim-Salman19/OCR/blob/main/docs/BENCHMARKS_2026.md)). Per-format conversion throughput (DOCX/PPTX/image assembly on top of that OCR pass) has not been independently benchmarked -- the "Throughput / Speed" column below says so rather than inventing a number.

| Input Source Format | Target Output Format | Throughput / Speed | Special Capabilities | Guide Link |
|---|---|---|---|---|
| **Scanned / Vector PDF** | **GitHub Markdown (.md)** | ~15.3s/page OCR pass (measured); Markdown assembly on top not separately benchmarked | Markdown tables, LaTeX equations, heading hierarchy | **[PDF to Markdown](pdf-to-markdown.md)** |
| **Scanned / Vector PDF** | **Microsoft Word (.docx)** | Not independently benchmarked | Editable paragraphs, native `w:tbl` XML tables | **[PDF to DOCX](scanned-pdf-to-docx.md)** |
| **PowerPoint (.pptx)** | **Markdown (.md)** | Not independently benchmarked | Embedded diagram OCR, presenter notes parsing | **[PPTX to Markdown](pptx-to-markdown.md)** |
| **Raster Image (PNG/JPG)** | **Dual-Layer PDF (.pdf)** | Not independently benchmarked | Exact word BBox coordinate text layer (PyMuPDF) | **[Image to Searchable PDF](image-to-searchable-pdf.md)** |
| **Scanned Math / Physics** | **LaTeX Equations ($...$)**| Not independently benchmarked | Inline & display mathematical notation recovery | **[PDF to LaTeX](pdf-to-latex.md)** |
| **Scanned Book / Archive** | **EPUB 3.0 Publication** | Bounded streaming (see the 1,000-page memory stress test) | Table of contents, reflowable text, e-reader ready | **[PDF to EPUB](pdf-to-epub.md)** |

---

## 🛠️ Universal Ingestion CLI
Every format conversion above is executable with a single unified CLI command:
```bash
python -m blast_ocr.cli <input_path> --formats md,docx,pdf,epub
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

