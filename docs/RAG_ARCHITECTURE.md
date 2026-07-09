# RAG Architecture Specification

This document details the data ingestion, text chunking, embedding generation, version isolation, and semantic lookup strategies implemented in **SupportGPT Enterprise**.

---

## 📥 Document Ingestion Pipeline

The ingestion system (`src/rag/ingestion.py`) parses enterprise files and extracts plain text structure:

- **PDF Ingestion**: Parses content page-by-page using `PyPDF2`.
- **DOCX Ingestion**: Loops through document paragraph logs using `python-docx`.
- **HTML Ingestion**: Trims scripts and stylesheets, extracting raw text nodes via `BeautifulSoup4`.
- **FAQ Ingestion**: Reads structured JSON blocks containing question/answer pairs.

---

## ✂️ Text Chunking Strategy

To fit document contexts within LLM context windows while preserving semantic meaning:
- We use a custom **RecursiveTextSplitter** (`src/rag/chunking.py`).
- **Chunk Size**: 600 characters (~150 tokens).
- **Chunk Overlap**: 120 characters (~30 tokens) to ensure semantic continuity between borders.
- Text is split hierarchically using separators: paragraphs (`\n\n`), newlines (`\n`), sentence endings (`. `, `? `, `! `), and spaces.

---

## 🏷️ Knowledge Base Versioning

Hiring managers value how systems manage knowledge rollbacks. SupportGPT implements version isolation:
- Documents are tagged with version identifiers (`v1`, `v2`, `v3`) in PostgreSQL.
- Embedded vectors are added to ChromaDB with version flags:
  ```python
  metadata = {"version": "v1", "doc_id": "refund_policy"}
  ```
- Vector queries are restricted by version tags, allowing instant content rolls, branching updates, or downgrades without re-indexing all files:
  ```python
  where_filter = {"version": active_version}
  ```

---

## 🔍 Hybrid Search, Reranking & Citations

- **Embedding Model**: OpenAI `text-embedding-3-small` (1536 dimensions) or Mock unit vectors in test mode.
- **Search distance metric**: Cosine similarity.
- **Hybrid retrieval**: `VectorStoreManager.query_kb` combines ChromaDB vector recall with a local BM25-style lexical scorer. Vector search fetches a wider candidate set, lexical search scores version/category-filtered KB chunks, and the reranker merges both signals.
- **Rerank weights**: Final ranking uses vector similarity, normalized lexical score, and a small exact-term overlap boost. This improves support-policy queries where exact terms such as order IDs, refund windows, product names, or warranty phrases matter.
- **Scope boundary**: The lexical scorer is lightweight and in-process. It is suitable for a resume/demo system and can be replaced by Elasticsearch/OpenSearch, Postgres full-text search, or a production reranker service.
- **Citations format**: Retrieved contexts are wrapped in a standard schema including the source name, matching score, and document version:
  ```json
  {
    "source": "Corporate Refund Policy (v1)",
    "text": "All billing refund requests must be filed within 30 days of payment.",
    "score": 0.98,
    "version": "v1"
  }
  ```
  This is rendered in the agent copilot view for human verification.
