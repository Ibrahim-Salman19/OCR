---
name: agentic-rag-connector
description: "Skill for connecting B.L.A.S.T. OCR Engine to modern agentic RAG architectures (LangChain, LlamaIndex, ChromaDB, Qdrant, Milvus, pgvector, Pinecone). Handles hierarchy-aware document chunking, metadata enrichment, formula preservation, and table indexing for high-precision retrieval."
version: 1.0.0
tags:
  - rag
  - langchain
  - llamaindex
  - vector-search
  - document-loaders
  - semantic-chunking
---

# Agentic RAG Connector Skill: B.L.A.S.T. OCR Pipeline

## 1. Context & Purpose

Standard naive text splitters break tabular structures, corrupt mathematical formulas, and sever heading hierarchies, causing severe retrieval failures in Retrieval-Augmented Generation (RAG).

The **B.L.A.S.T. OCR RAG Connector** provides deterministic, structure-preserving document ingestion:
- **Preserves Hierarchical TOCs**: Links chunks to parent sections (e.g. `Chapter 3 > Section 3.2 > Methodology`).
- **Atomic Table Extraction**: Keeps tables intact as Markdown or HTML rather than splitting mid-row.
- **LaTeX Math Preservation**: Encapsulates formulas in KaTeX delimiters for LLM math comprehension.
- **Enriched Metadata**: Attaches page numbers, bounding boxes, OCR confidence scores, and source file paths.

---

## 2. Integration Recipes

### 2.1 LangChain Native Ingestion
```python
from blast_ocr.integrations import BlastOCRDocumentLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# Step 1: Load structured document
loader = BlastOCRDocumentLoader(
    file_path="paper.pdf",
    extract_tables=True,
    extract_formulas=True
)
documents = loader.load()

# Step 2: Semantic vector storage
vectorstore = Chroma.from_documents(
    documents=documents,
    embedding=OpenAIEmbeddings()
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
```

### 2.2 LlamaIndex Native Ingestion
```python
from blast_ocr.integrations import BlastOCRReader
from llama_index.core import VectorStoreIndex

# Step 1: Read with B.L.A.S.T.
reader = BlastOCRReader()
documents = reader.load_data(file_path="quarterly_financials.pdf")

# Step 2: Build query engine
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()
response = query_engine.query("What was the total operating revenue for Q3?")
```

### 2.3 Structure-Aware Semantic Chunker (Built-In)
```python
from blast_ocr.core.semantic_chunker import SemanticChunker

chunker = SemanticChunker(max_tokens=512, overlap_tokens=64)
chunks = chunker.chunk_document(markdown_text, toc_tree=toc_metadata)

for chunk in chunks:
    print(f"Section: {chunk['hierarchy']} | Page: {chunk['page']} | Tokens: {chunk['token_count']}")
```

---

## 3. Best Practices for High-Precision Agentic Retrieval
1. **Never split tables across chunks**: Enable `atomic_tables=True` to ensure table grids remain coherent.
2. **Include Header Lineage**: Prepend the section breadcrumb (e.g. `# Financial Performance > EBITDA`) to every vector chunk.
3. **Filter by Confidence**: Discard or flag low-confidence OCR fragments (< 0.70) during ingestion.
