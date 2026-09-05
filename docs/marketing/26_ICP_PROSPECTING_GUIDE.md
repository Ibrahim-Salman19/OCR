# 🎯 ICP Prospecting Guide & Enterprise Account Qualification Matrix

**Status**: 🟢 Production-Grade  
**Applicable Skills**: `prospecting`, `revops`, `sales-enablement`, `cold-email`  
**Target Profiles**: Series A-D AI Startups, Enterprise FinTech, HealthTech, LegalTech, Platform Engineering Teams

---

## 🔍 1. Boolean Search Query Bank

Use these exact queries across LinkedIn Sales Navigator, Apollo.io, and Google Search to identify high-intent accounts and buyers.

### A. LinkedIn Sales Navigator Search Strings
```text
Title: ("Head of AI" OR "VP of Artificial Intelligence" OR "Lead Machine Learning Engineer" OR "Staff ML Engineer" OR "VP Engineering" OR "Head of Platform" OR "Lead Data Engineer" OR "Director of Engineering")
AND
Keywords: ("OCR" OR "Document Processing" OR "Document Intelligence" OR "RAG" OR "Unstructured Data" OR "PDF Extraction" OR "Computer Vision" OR "Tesseract" OR "Textract")
AND
Company Headcount: 50-500 (Mid-Market High Velocity) OR 500-10,000 (Enterprise Air-Gapped)
AND
Industry: ("Computer Software" OR "Financial Services" OR "Hospital & Health Care" OR "Legal Services" OR "Information Technology")
AND
Geography: United States, United Kingdom, Canada, European Union
```

### B. Apollo.io Search Filters
- **Technologies Used**: Python, Docker, Kubernetes, Redis, PyTorch, ONNX, LangChain, LlamaIndex, AWS Textract, Google Cloud Vision, Azure Cognitive Services.
- **Job Postings / Hiring Signals**: Hiring for "Document Processing Engineer", "OCR Specialist", "RAG Pipeline Engineer", "LLM Platform Engineer".
- **Department**: Engineering & Technical, Information Technology, AI/Data Science.
- **Funding Stage**: Seed, Series A, Series B, Series C, Private Equity.

### C. Google X-Ray Search Queries
```text
site:linkedin.com/in/ ("Head of AI" OR "Staff Machine Learning Engineer") ("document parsing" OR "PDF" OR "OCR") ("Python" OR "FastAPI") -recruiter -hiring
```

---

## 🐙 2. GitHub Stargazer & Repository Mining Engine

Prospects who star, fork, or open issues on legacy OCR or document parsing repositories represent immediate high-intent leads experiencing active pain points.

### Target Repositories to Mine:
1. `tesseract-ocr/tesseract` (Issues discussing performance, memory leaks, slow throughput)
2. `JaidedAI/EasyOCR` (Issues discussing GPU memory exhaustion, batch inference)
3. `VikParuchuri/marker` (Issues regarding heavy VRAM requirements or table hallucinations)
4. `DS4SD/docling` (Users seeking faster CPU throughput or offline deployment)
5. `Unstructured-IO/unstructured` (Users complaining about cloud API pricing or slow chunking)

### GitHub API Mining Script (`scripts/mine_github_leads.py`):
```python
import os
import requests

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

TARGET_REPOS = [
    "tesseract-ocr/tesseract",
    "JaidedAI/EasyOCR",
    "VikParuchuri/marker",
    "DS4SD/docling",
]

def extract_repo_stargazers(repo: str, max_pages: int = 5):
    leads = []
    for page in range(1, max_pages + 1):
        url = f"https://api.github.com/repos/{repo}/stargazers?page={page}&per_page=100"
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            break
        for user in resp.json():
            user_data = requests.get(user["url"], headers=HEADERS).json()
            if user_data.get("email") or user_data.get("company"):
                leads.append({
                    "username": user_data.get("login"),
                    "name": user_data.get("name"),
                    "company": user_data.get("company"),
                    "email": user_data.get("email"),
                    "bio": user_data.get("bio"),
                    "source_repo": repo
                })
    return leads
```

---

## 📊 3. The 100-Point Account Fit Scoring Matrix

Every inbound and outbound account is scored out of 100 points before SDR assignment:

```
+-----------------------------------------------------------------------------------+
| DIMENSION                     | CRITERIA                               | POINTS   |
+-----------------------------------------------------------------------------------+
| 1. Document Volume (30 pts)   | > 1,000,000 pages / month              | 30 pts   |
|                               | 200,000 - 1,000,000 pages / month      | 20 pts   |
|                               | 25,000 - 200,000 pages / month         | 10 pts   |
|                               | < 25,000 pages / month                 | 0 pts    |
+-----------------------------------------------------------------------------------+
| 2. Regulatory & Privacy (25)  | Strict Air-Gap / HIPAA / SOC2 / FedRAMP| 25 pts   |
|                               | EU GDPR Cross-Border Data Constraints  | 15 pts   |
|                               | Standard Commercial Privacy            | 5 pts    |
+-----------------------------------------------------------------------------------+
| 3. Infrastructure Match (20)  | Kubernetes / Docker / Redis in Stack   | 20 pts   |
|                               | Bare-Metal Linux Servers               | 15 pts   |
|                               | Serverless Only (AWS Lambda)           | 5 pts    |
+-----------------------------------------------------------------------------------+
| 4. Pain Trigger Signals (15)  | Cloud OCR Bill > $3,000/mo             | 15 pts   |
|                               | Active OOM / Memory Leak GitHub Issues | 10 pts   |
|                               | RAG Table Hallucination Complaints     | 10 pts   |
+-----------------------------------------------------------------------------------+
| 5. Team Authority (10 pts)    | VP AI / Head of Platform / CTO engaged | 10 pts   |
|                               | Senior / Staff Engineer engaged        | 7 pts    |
|                               | Junior Dev / Intern                    | 2 pts    |
+-----------------------------------------------------------------------------------+
```

### Action Thresholds:
- **85 - 100 Points (Tier 1 Strategic)**: Direct AE executive outreach + custom 14-day Staging Pilot Sprint + dedicated Slack connect.
- **60 - 84 Points (Tier 2 High Growth)**: Automated 4-step personalized email sequence + interactive ROI calculator link.
- **Below 60 Points (Tier 3 Product-Led)**: Self-serve Open Source Community edition onboarding + automated weekly newsletter.

---

## 📋 4. Tier 1 Account Qualification Checklist (BANT/MEDDPICC)

When an SDR or AE conducts an initial discovery call, verify:

1. **Metrics**:
   - What is the current monthly document volume (PDF, scans, forms)?
   - What is the average document processing latency required (real-time vs batch)?
   - What is the current cloud OCR monthly spend?
2. **Economic Buyer**:
   - Who owns the budget for platform infrastructure and cloud compute?
   - Is the VP of Engineering or Head of AI signed off on offline execution?
3. **Decision Criteria**:
   - What are the required output formats (Markdown, DOCX, Searchable PDF, JSON)?
   - What is the minimum acceptable Character Error Rate (CER)? (B.L.A.S.T. baseline: 0.1916).
   - Are tables and mathematical formulas required?
4. **Decision Process**:
   - Does InfoSec require an air-gapped security audit?
   - What is the procurement timeline (typically 14-day staging pilot $\rightarrow$ production rollout)?
5. **Identify Pain**:
   - Have they experienced unhandled OOM crashes or memory leaks on long PDFs?
   - Are cloud API latency spikes degrading user experience in their RAG application?
6. **Champion**:
   - Has a lead engineer run the `pip install blast-ocr` CLI locally and confirmed the 29.1 pps speedup?
