# Directory & Awesome-List Submission Drafts

Drafted text only — not submitted. Each of these is a PR or form submission on someone else's project under your GitHub identity, so that's yours to send, not something to automate. Same verified-numbers rule as `launch_copy.md`: don't add a claim these drafts don't already have a source for.

## MCP server directories

Concrete surfaces, in rough order of relevance to an MCP-native OCR tool:

1. **Official MCP servers list** — modelcontextprotocol.io/servers (community servers section; submission is a PR to the `servers` repo under the `modelcontextprotocol` GitHub org).
2. **Smithery** — smithery.ai (MCP server registry with one-click install; has its own submission/claim flow on the site).
3. **mcp.so** — community-run MCP directory, PR or form-based submission.
4. **PulseMCP** — pulsemcp.com, has a submission form for new servers.
5. **Glama.ai MCP directory** — glama.ai/mcp/servers, has a submission flow.

Check each site's current submission process before sending — these directories are new and their intake mechanics (PR vs. form vs. auto-crawl from a registry file) change often.

**Draft entry (adapt per site's required fields):**

- **Name:** B.L.A.S.T. OCR
- **One-line description:** Self-hosted OCR and document-intelligence MCP server — PDF/PPTX/image to Markdown, tables, LaTeX math, and dual-layer searchable PDF, fully offline.
- **Repo:** https://github.com/Ibrahim-Salman19/OCR
- **Install:** `python3 -m blast_ocr.mcp_server`, or add to `mcp.json` / `claude_desktop_config.json`:
  ```json
  {
    "mcpServers": {
      "blast-ocr": {
        "command": "python3",
        "args": ["-m", "blast_ocr.mcp_server"]
      }
    }
  }
  ```
- **Tools exposed:** `blast_ocr_process`, `blast_ocr_extract_tables`, `blast_ocr_extract_formulas`, `blast_ocr_semantic_chunk` (job-status querying is REST-only, `GET /v1/ocr/jobs/{job_id}`, not yet an MCP tool)
- **License:** MIT
- **Category/tags:** document processing, OCR, PDF, RAG

## Awesome-list entries

Single-line format most awesome-lists expect — adjust wording to match the target list's existing entry style before submitting (they're usually strict about format via a linter/CI check on the PR):

- **awesome-mcp-servers:**
  `- [B.L.A.S.T. OCR](https://github.com/Ibrahim-Salman19/OCR) - Self-hosted OCR and document-intelligence MCP server: PDF/PPTX/image to Markdown, table extraction, and LaTeX math, fully offline.`

- **awesome-ocr:**
  `- [B.L.A.S.T. OCR](https://github.com/Ibrahim-Salman19/OCR) - Self-hosted Python OCR engine (RapidOCR/ONNX) with table extraction, LaTeX math recognition, and dual-layer searchable PDF output.`

- **awesome-python:**
  `- [B.L.A.S.T. OCR](https://github.com/Ibrahim-Salman19/OCR) - Self-hosted OCR and document-intelligence pipeline with a native MCP server and LangChain/LlamaIndex loaders.`

Before submitting to any of these: re-read the target list's `CONTRIBUTING.md` — most require alphabetical placement in the right category, a working link check, and sometimes a minimum-stars or minimum-age bar that a 0-star repo may not yet clear. Worth checking each list's actual bar before spending a PR on it.
