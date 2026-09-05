# Video Production Scripts & Storyboards: B.L.A.S.T. OCR Engine

**Document Version**: 3.0.0  
**Frameworks**: Hyperframes (HTML/CSS), Remotion (React), CapCut & Descript  
**Supported Aspect Ratios**: 16:9 Landscape (YouTube, Homepage, Docs), 9:16 Vertical (Shorts, Reels, TikTok), 1:1 Square (LinkedIn, Twitter/X)  

---

## 1. Video Production Architecture & Strategy

Video is the highest-conversion distribution medium for developer tools when executed with zero marketing fluff and 100% technical proof. Following the `video` skill guidelines:
1. **The 3-Second Rule**: Hook viewers immediately with a combined [VISUAL HOOK] + [VERBAL HOOK] + [TEXT OVERLAY].
2. **Show, Don't Tell**: Begin with the terminal running and documents transforming in real-time before introducing architecture.
3. **No Uncanny Avatars for Technical Demos**: Use real developer screen captures with programmatic HTML overlays (Hyperframes) and high-contrast monospace typography.
4. **Captions on Everything**: 85% of social video is consumed on mute. Max 2 lines on screen, 3-5 words per line, highlighted key metrics.

---

## 2. Video 1: 90-Second Flagship Product Launch Video

- **Target Platforms**: GitHub README Hero, Homepage, YouTube, Hacker News Show HN
- **Format**: 16:9 Landscape (1920x1080 @ 60fps)
- **Audio Profile**: Cyberpunk / Minimal Tech ambient synth bed with crisp mechanical keyboard foley and clean studio voiceover (mid-Atlantic, calm, authoritative).

### Beat-by-Beat Production Table

| Timecode | Scene Description | Visual Cue & Animation | Audio & Voiceover (VO) | On-Screen Text (OST) |
|:---:|:---|:---|:---|:---|
| **0:00 - 0:05** | **The Hook: The Crash** | Split-screen: Left side shows a generic Python script crashing with `MemoryError: Out of Memory` at page 842. Right side shows a $14,800 monthly AWS Textract invoice. | VO: "Your cloud OCR bill is out of control. And your local Python scripts crash when you feed them an 800-page book." | `FATAL: OOM CRASH (Page 842)` / `Cloud OCR Invoice: $14,800` |
| **0:05 - 0:15** | **The Reveal: B.L.A.S.T.** | Dynamic punch-in to an electric neon terminal. A single CLI command executes: `python run.py 1000_pages.pdf --formats md,pdf`. Terminal log streams at 29 pages per second with memory flatlined at 142 MB. | VO: "Meet B.L.A.S.T. OCR. The deterministic, air-gapped document intelligence engine built for high-throughput batch execution." | `python run.py 1000_pages.pdf` / `29.1 Pages/Sec • 0.0002 MB/Page Slope` |
| **0:15 - 0:30** | **Architectural Pillar 1: ONNX Speed** | 3D animated diagram of ONNX Runtime multi-provider fallback hierarchy: CUDA (GPU) → DirectML (Windows) → CPU SIMD. Comparison bar chart against EasyOCR. | VO: "Powered by vectorized ONNX Runtime execution, B.L.A.S.T. cuts CPU latency by 7.7x and reduces Character Error Rate by 18% versus PyTorch baselines." | `7.7x Faster than EasyOCR` / `CUDA → DirectML → CPU Fallback` |
| **0:30 - 0:45** | **Architectural Pillar 2: Table Reconstruction** | A messy scanned financial balance sheet with merged cells and bordered lines morphs into a clean, perfectly aligned GitHub Flavored Markdown table in VS Code. | VO: "It doesn't just dump word soup. Morphological layout analyzers reconstruct complex multi-column tables directly into GitHub Flavored Markdown and HTML." | `Morphological Table Extraction` / `Scored with Built-in TEDS Evaluator` |
| **0:45 - 0:58** | **Architectural Pillar 3: LaTeX Math Parsing** | A camera zoom on a physics textbook page with double integrals and square roots. KaTeX equations render instantly in real-time in an Obsidian note preview. | VO: "Textbook equations and scientific research papers are automatically extracted into clean inline and display LaTeX syntax." | `LaTeX Formula Extraction` / `$...$ and $$...$$ KaTeX Markdown` |
| **0:58 - 1:12** | **Architectural Pillar 4: Native MCP & AI Agent RAG** | Cursor IDE and Claude Desktop UI appears. User asks Claude: @blast-ocr process this archive. B.L.A.S.T. stdio MCP server executes tools `blast_ocr_process` and returns structured JSON chunks. | VO: "Connect B.L.A.S.T. directly to Claude Desktop, Cursor, or your LangChain and LlamaIndex agents with native Model Context Protocol support." | `Native MCP Server (mcp.json)` / `Zero-Hallucination Agentic RAG` |
| **1:12 - 1:22** | **Privacy & Sandboxing** | Vault lock animation with security badges: HIPAA, GDPR, SOC 2, Air-Gapped. PII redactor automatically blacks out credit cards and SSNs. | VO: "Zero cloud telemetry. 100% offline. Automated 8-class forensic PII redaction ensures your confidential records never leave your infrastructure." | `100% Offline • Zero Telemetry` / `Forensic 8-Class PII Masking` |
| **1:22 - 1:30** | **Call to Action (CTA)** | Clean terminal prompt showing pip install command and GitHub repo star animation. | VO: "Take back your document sovereignty. Pip install blast-ocr, clone the repo on GitHub, or launch the interactive live demo today." | `pip install blast-ocr` / `github.com/Ibrahim-Salman19/OCR` |

---

## 3. Video 2: 3-Minute Developer MCP Walkthrough & Live Coding

- **Target Platforms**: YouTube Technical Tutorial, Docs Embedding (`docs/AI_AGENT_INTEGRATION_GUIDE.md`)
- **Format**: 16:9 Landscape (1920x1080 @ 60fps)
- **Presenter**: Developer screen recording with picture-in-picture webcam, VS Code dark theme, terminal.

### Step-by-Step Script & Code Demonstration

#### 0:00 - 0:30 | Introduction & Problem Setup
```
[Visual]: Developer on webcam in corner. Main screen shows Claude Desktop with a 200-page scanned legal contract.
[VO]: "If you have ever tried dragging a 100-page scanned PDF into Claude Desktop or Cursor, you know the pain: token limit exceeded, broken formatting, or Claude hallucinates numbers because the OCR was garbled. Today, I am showing you how to give Claude Desktop and Cursor deterministic, local OCR superpowers using B.L.A.S.T. and Model Context Protocol in less than two minutes."
```

#### 0:30 - 1:15 | Configuring the MCP Server in Claude Desktop
```
[Visual]: Developer opens terminal and types:
pip install blast-ocr

Developer opens ~/Library/Application Support/Claude/claude_desktop_config.json
Adds the configuration block:
```
```json
{
  "mcpServers": {
    "blast-ocr": {
      "command": "python3",
      "args": ["-m", "blast_ocr.mcp_server"],
      "env": {
        "BLAST_OCR_ENGINE": "rapidocr",
        "BLAST_OCR_SECURE_MODE": "true"
      }
    }
  }
}
```
```
[VO]: "We install blast-ocr, then add the blast-ocr server to claude_desktop_config.json. Notice the environment variables: we are selecting the RapidOCR ONNX backend and enabling secure mode, which automatically masks sensitive PII like SSNs and credit cards before returning text to the LLM."
```

#### 1:15 - 2:05 | Live Tool Invocation in Claude Desktop
```
[Visual]: Developer restarts Claude Desktop. The hammer icon in Claude lights up showing 4 new tools:
- blast_ocr_process
- blast_ocr_extract_tables
- blast_ocr_extract_formulas
- blast_ocr_semantic_chunk

Developer types:
"Claude, use blast_ocr_extract_tables on ./financial_filing.pdf and give me a summary of EBITDA across Q1 to Q4."

[Visual]: Claude calls blast_ocr_extract_tables. B.L.A.S.T. processes the PDF in 1.4 seconds. A clean GFM table appears with accurate EBITDA metrics.
[VO]: "Look at that speed. Claude invokes the local tool, B.L.A.S.T. analyzes the morphological grid structure offline, and returns pure Markdown. Zero token bloat, zero hallucination."
```

#### 2:05 - 2:45 | Connecting to Cursor & LangChain RAG
```
[Visual]: Screen cuts to Cursor IDE. Developer opens .cursorrules and demonstrates BlastOCRDocumentLoader in a LangChain Python script:
```
```python
from blast_ocr.integrations import BlastOCRDocumentLoader

loader = BlastOCRDocumentLoader(
    file_path="research_paper.pdf",
    extract_tables=True,
    extract_formulas=True
)
docs = loader.load()
print(f"Loaded {len(docs)} hierarchy-aware chunks with KaTeX math!")
```
```
[VO]: "For agentic RAG architectures, B.L.A.S.T. provides native LangChain and LlamaIndex loaders that preserve headers and math expressions, giving your vector embeddings 3x higher semantic retrieval precision."
```

#### 2:45 - 3:00 | Summary & Outro
```
[Visual]: Return to full-screen terminal and repository GitHub page.
[VO]: "B.L.A.S.T. OCR is completely open-source under the MIT license. Check out the documentation link below to star the repo and join our developer Discord."
[OST]: github.com/Ibrahim-Salman19/OCR • Star on GitHub!
```

---

## 4. Video 3: 30-Second Short-Form Vertical Ad (TikTok / Reels / Shorts)

- **Target Platforms**: TikTok, YouTube Shorts, Instagram Reels
- **Format**: 9:16 Vertical (1080x1920 @ 60fps)
- **Style**: Ultra-fast kinetic typography, punch-in cuts every 1.5 seconds, trending tech audio beat.

```
[0:00 - 0:03] | THE 3-SECOND HOOK
[VISUAL HOOK]: Extreme close-up of a phone screen with red text "AWS BILL: $4,210.80". Phone violently smashes onto desk (sound: glass thud).
[VERBAL HOOK]: "Stop paying AWS for OCR that still messes up your tables!"
[TEXT OVERLAY]: "AWS TEXTRACT: $4,210 💀"

[0:03 - 0:10] | THE AGITATION
[VISUAL]: Screen recording of PyTorch script throwing CUDA Out Of Memory at 3 AM. Red error text flashes.
[VERBAL]: "And stop writing Python scripts that crash every time you process an 800-page book."
[TEXT OVERLAY]: "CUDA OOM: Page 842 ❌"

[0:10 - 0:22] | THE SOLUTION
[VISUAL]: Fast montage:
1. Terminal running: "python run.py book.pdf --formats md,pdf"
2. RapidOCR ONNX processing at 29 pages per second.
3. Complex table snaps into beautiful Notion Markdown.
4. Physics equation $\oint ec{B} \cdot dec{A} = 0$ renders in LaTeX.
[VERBAL]: "Switch to B.L.A.S.T. OCR. Runs 100% offline on ONNX. 7.7x faster than EasyOCR. Extracts tables and LaTeX math. Zero memory leaks on 1,000 pages."
[TEXT OVERLAY]: "29 Pages/Sec ⚡ • 0% Memory Leaks 🔒 • Free & Open Source"

[0:22 - 0:30] | THE CALL TO ACTION
[VISUAL]: B.L.A.S.T. logo pulses with electric blue neon. GitHub repository page shows 737 passing tests badge.
[VERBAL]: "100% free and MIT licensed. Link in bio to star the repo and try the live demo!"
[TEXT OVERLAY]: "Link in Bio • pip install blast-ocr 🚀"
```

---

## 5. Programmatic Video Pipeline: Hyperframes Implementation

To generate batch video changelogs and social announcement clips deterministically from code, B.L.A.S.T. utilizes **Hyperframes** (`npm install hyperframes`):

```typescript
// scripts/generate_release_video.ts
import { render } from "hyperframes";

async function generatePromoVideo() {
  await render({
    frames: [
      {
        html: `
          <div style="background: #0E1117; color: #FFFFFF; height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; font-family: sans-serif;">
            <h1 style="font-size: 80px; color: #00F2FE; margin-bottom: 20px;">B.L.A.S.T. OCR</h1>
            <p style="font-size: 36px; color: #10B981;">The Sovereign Document Intelligence Engine</p>
          </div>
        `,
        duration: 3,
      },
      {
        html: `
          <div style="background: #0E1117; color: #FFFFFF; height: 100vh; padding: 100px; font-family: monospace;">
            <h2 style="font-size: 48px; color: #F59E0B;">$ python run.py archive.pdf</h2>
            <p style="font-size: 32px; color: #10B981; margin-top: 40px;">✔ 1,000 pages streamed</p>
            <p style="font-size: 32px; color: #10B981;">✔ Memory Leak Slope: 0.0002 MB/page</p>
            <p style="font-size: 32px; color: #00F2FE;">✔ 7.7x Faster than EasyOCR</p>
          </div>
        `,
        duration: 4,
      },
      {
        html: `
          <div style="background: #0E1117; color: #FFFFFF; height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; font-family: sans-serif;">
            <h2 style="font-size: 64px; color: #FFFFFF;">Try the Live Demo</h2>
            <p style="font-size: 40px; color: #00F2FE; margin-top: 20px;">ocr-book.streamlit.app</p>
            <p style="font-size: 32px; color: #64748B; margin-top: 40px;">MIT Licensed • 100% Offline</p>
          </div>
        `,
        duration: 3,
      }
    ],
    output: "dist/blast_ocr_v3_teaser.mp4",
    width: 1920,
    height: 1080,
    fps: 30
  });
}

generatePromoVideo();
```
