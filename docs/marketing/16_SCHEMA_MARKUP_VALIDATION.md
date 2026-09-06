# Schema.org JSON-LD Structured Data & Rich Results Audit: B.L.A.S.T. OCR Engine

This document details the multi-entity Schema.org JSON-LD `@graph` architecture deployed across **B.L.A.S.T. OCR Engine**, verifying rich snippet eligibility for Google, Bing, and AI search crawlers.

---

## 1. Multi-Entity `@graph` Architecture

The structured data is embedded directly into the live DOM via Streamlit (`blast_ocr/ui/web_app.py`) and served via the REST API endpoint at `/v1/schema.json`.

```
                  ┌───────────────────────────────────────────────┐
                  │          SCHEMA.ORG JSON-LD @GRAPH            │
                  └───────────────────────────────────────────────┘
                                         │
        ┌───────────────────┬────────────┴───────┬───────────────────┐
        ▼                   ▼                    ▼                   ▼
┌──────────────┐    ┌──────────────┐     ┌──────────────┐    ┌──────────────┐
│  SOFTWARE    │    │   SOFTWARE   │     │   DATASET    │    │   FAQPAGE    │
│ APPLICATION  │    │ SOURCE CODE  │     │ (14-Page     │    │ (8 Question  │
│ (Core Engine)│    │ (GitHub Repo)│     │  Gold Corpus)│    │  Answer Pairs)
└──────────────┘    └──────────────┘     └──────────────┘    └──────────────┘
        │                   │                    │                   │
        └───────────────────┴────────────┬───────┴───────────────────┘
                                         ▼
                                ┌──────────────────┐
                                │   ORGANIZATION   │
                                │ (B.L.A.S.T. Team)│
                                └──────────────────┘
```

---

## 2. Canonical JSON-LD Implementation (Served on `/v1/schema.json`)

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "SoftwareApplication",
      "@id": "https://blast-ocr.dev/#application",
      "name": "B.L.A.S.T. OCR Engine",
      "applicationCategory": "DeveloperApplication",
      "operatingSystem": "Linux, Windows, macOS",
      "softwareVersion": "2.0.0",
      "description": "Deterministic, air-gapped document intelligence and high-throughput OCR engine with bounded streaming memory and zero memory leaks.",
      "offers": {
        "@type": "Offer",
        "price": "0.00",
        "priceCurrency": "USD"
      },
      "author": {
        "@id": "https://ibrahimsalman.vercel.app/#person"
      }
    },
    {
      "@type": "Person",
      "@id": "https://ibrahimsalman.vercel.app/#person",
      "name": "Ibrahim Salman",
      "alternateName": ["Ibrahim-Salman19", "Ibrahim Salman Dev"],
      "url": "https://ibrahimsalman.vercel.app",
      "image": "https://ibrahimsalman.vercel.app/profile.jpg",
      "jobTitle": "Full-Stack Software Engineer & AI Systems Architect",
      "email": "mailto:ibrahim.pk848@gmail.com",
      "alumniOf": {
        "@type": "CollegeOrUniversity",
        "name": "University of Engineering and Technology, Taxila",
        "url": "https://uettaxila.edu.pk/",
        "sameAs": "https://www.wikidata.org/wiki/Q10854449"
      },
      "knowsAbout": [
        "Optical Character Recognition (OCR)",
        "Retrieval-Augmented Generation (RAG)",
        "Document Intelligence",
        "Computer Vision",
        "ONNX Runtime Multi-Provider Acceleration",
        "Distributed Task Queues & Swarms",
        "Python",
        "TypeScript"
      ],
      "sameAs": [
        "https://github.com/Ibrahim-Salman19",
        "https://www.linkedin.com/in/ibrahim-salman-dev/",
        "https://www.upwork.com/freelancers/~013e1c54e9a3f7a2b8",
        "https://x.com/ibrahim_salman19"
      ]
    },
    {
      "@type": "SoftwareSourceCode",
      "@id": "https://blast-ocr.dev/#sourcecode",
      "name": "B.L.A.S.T. OCR Core Engine Source",
      "programmingLanguage": "Python, C++",
      "runtimePlatform": "Python 3.10+, ONNX Runtime 1.17+",
      "codeRepository": "https://github.com/Ibrahim-Salman19/OCR",
      "license": "https://opensource.org/licenses/MIT"
    },
    {
      "@type": "Dataset",
      "@id": "https://blast-ocr.dev/#dataset",
      "name": "B.L.A.S.T. 14-Page Gold Standard OCR Benchmark Corpus",
      "description": "Standardized evaluation corpus consisting of 14 complex scanned documents containing degraded text, multi-column tables, and Nastaliq Urdu script.",
      "license": "https://creativecommons.org/licenses/by/4.0/",
      "creator": {
        "@id": "https://blast-ocr.dev/#organization"
      }
    },
    {
      "@type": "FAQPage",
      "@id": "https://blast-ocr.dev/#faq",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "What is B.L.A.S.T. OCR Engine and how fast is it?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "B.L.A.S.T. OCR Engine is a deterministic, air-gapped document intelligence system that processes scanned PDFs and images at 29.1 pages per second on CPU and 85+ pages per second on GPU with zero memory leaks."
          }
        },
        {
          "@type": "Question",
          "name": "How does B.L.A.S.T. OCR prevent memory leaks on 1,000+ page documents?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "B.L.A.S.T. OCR enforces bounded memory streaming via a sliding-window chunking buffer, maintaining a verified 0.0002 MB/page memory leak slope across 1,000 consecutive pages."
          }
        }
      ]
    },
    {
      "@type": "HowTo",
      "@id": "https://blast-ocr.dev/#howto-mcp",
      "name": "How to Connect B.L.A.S.T. OCR to Claude Desktop via MCP",
      "step": [
        {
          "@type": "HowToStep",
          "name": "Install B.L.A.S.T. OCR",
          "text": "Run pip install blast-ocr in your terminal environment."
        },
        {
          "@type": "HowToStep",
          "name": "Configure Claude Desktop",
          "text": "Add blast-ocr under mcpServers in your claude_desktop_config.json pointing to python3 -m blast_ocr.mcp_server."
        }
      ]
    },
    {
      "@type": "Organization",
      "@id": "https://blast-ocr.dev/#organization",
      "name": "B.L.A.S.T. OCR Open Source Initiative",
      "url": "https://blast-ocr.dev",
      "logo": "https://blast-ocr.dev/static/logo.png"
    }
  ]
}
```

---

## 3. Rich Results Eligibility Matrix

**Corrected 2026-09-06**: The original version of this table claimed unconditional Google SERP
rich-result eligibility for every entity. That's no longer accurate for two of the five rows.
Google restricted FAQ rich results to well-known government and health sites, and discontinued
HowTo rich results entirely (desktop and mobile), in its August 2023 policy update — this project
doesn't qualify for either. The markup itself is not wasted: GEO consumers (Perplexity, Bing
Copilot, ChatGPT Search, and other LLM-based answer engines) parse `FAQPage`/`HowTo` JSON-LD
directly regardless of Google's SERP display policy, so it's kept for that purpose, not for a
Google rich card that will not render.

| Search Feature | Targeted Entity | Google SERP Eligibility | GEO / AI-Answer-Engine Impact |
|---|---|:---:|---|
| **Software App Rich Card** | `SoftwareApplication` | ⚠️ Partial — no star rating shown (this project deliberately omits `aggregateRating`/`review`; see `docs/GEO_AND_SEO_OPTIMIZATION.md` §2 on why fabricated ratings are excluded) | Still fully machine-readable: name, price, OS, and feature list are extractable by any LLM or agent that fetches the page. |
| **FAQ Accordion Snippet** | `FAQPage` | ❌ Not eligible — restricted to well-known government/health domains since Google's Aug 2023 policy change | Directly quotable Q&A pairs for AI Overviews, Perplexity, and ChatGPT Search citation extraction. |
| **Dataset Badge** | `Dataset` | ✅ Yes (name, license, description) | Indexed in Google Dataset Search for academic and research visibility. |
| **HowTo Interactive Steps**| `HowTo` | ❌ Removed — Google discontinued HowTo rich results (desktop and mobile) in Aug 2023 | Structured step sequence remains parseable by AI agents building install/setup instructions. |
| **Knowledge Graph Card** | `Organization` / `Person` | ⚠️ Not guaranteed — `sameAs` and entity markup aid disambiguation, but Knowledge Panel inclusion is an algorithmic Google decision, not something schema alone grants | Strengthens author/entity resolution for AI systems cross-referencing `sameAs` links (GitHub, LinkedIn, Upwork). |

---

## 4. Automated Verification Test
To verify the structured data on the running FastAPI service:
```bash
curl -s http://localhost:8000/v1/schema.json | python3 -m json.tool | grep -E "@type|name"
```
Outputs clean, unescaped JSON matching Schema.org standards.
