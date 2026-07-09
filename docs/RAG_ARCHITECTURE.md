# RAG 架构说明

本文说明 **SupportGPT Enterprise** 中的文档解析、文本切分、Embedding、知识库版本隔离、混合检索、rerank 和 citation 设计。

---

## 文档解析流程

文档解析模块位于 `src/rag/ingestion.py`，负责把企业知识库文件转换成纯文本：

- **PDF 解析**：使用 `PyPDF2` 按页提取文本。
- **DOCX 解析**：使用 `python-docx` 遍历段落内容。
- **HTML 解析**：使用 `BeautifulSoup4` 去除脚本和样式，提取可见文本。
- **FAQ 解析**：读取结构化 JSON 中的问题和答案。

---

## 文本切分策略

为了让知识库内容适配 LLM 上下文窗口，同时保留语义连续性：

- 使用自定义 `RecursiveTextSplitter`，位置在 `src/rag/chunking.py`。
- 默认 chunk size 为 600 字符，约 150 tokens。
- 默认 chunk overlap 为 120 字符，约 30 tokens。
- 按段落、换行、句号、问号、感叹号和空格递归切分。

---

## 知识库版本管理

系统支持知识库版本隔离，便于灰度上线、回滚和不同版本规则对比：

- 文档在数据库中通过 `version` 字段标记，例如 `v1`、`v2`。
- 向量写入 ChromaDB 时同步写入版本 metadata：

```python
metadata = {"version": "v1", "doc_id": "refund_policy"}
```

- 查询时使用 metadata filter 限定版本：

```python
where_filter = {"version": active_version}
```

---

## 混合检索、Rerank 与引用

- **Embedding 模型**：支持 OpenAI `text-embedding-3-small`，本地 demo 默认使用 mock embedding。
- **向量距离**：ChromaDB collection 使用 cosine similarity。
- **混合检索**：`VectorStoreManager.query_kb` 同时使用 ChromaDB 向量召回和本地 BM25 风格关键词打分。
- **候选扩展**：向量检索会多取候选，关键词检索会在版本和类别过滤后的 chunk 中计算 lexical score。
- **轻量 rerank**：最终分数融合向量相似度、归一化关键词分数和精确词重合 boost。
- **适用场景**：客服政策中常见的退款窗口、订单号、产品名、保修短语等精确词会被更稳定地召回。
- **边界说明**：当前 lexical scorer 是进程内轻量实现，适合简历项目和 demo。生产系统可替换为 Elasticsearch、OpenSearch、PostgreSQL full-text search 或 cross-encoder reranker。

引用结果统一封装为 `Citation`：

```json
{
  "source": "Corporate Refund Policy (v1)",
  "text": "All billing refund requests must be filed within 30 days of payment.",
  "score": 0.98,
  "version": "v1"
}
```

这些 citation 会返回给客服侧，用于人工核查 AI 回复是否有知识库依据。
