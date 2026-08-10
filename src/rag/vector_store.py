import os
import math
import re
from collections import Counter
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from src.config import settings
from src.rag.embedding import embedding_provider
from src.models.schemas import Citation

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "for", "from",
    "how", "i", "in", "is", "it", "of", "on", "or", "our", "the", "to",
    "we", "what", "when", "where", "with", "you", "your"
}

class VectorStoreManager:
    """负责 ChromaDB 向量存储和 Hybrid RAG 检索。

    支持知识库版本、类别过滤、词法融合和轻量 rerank。
    """
    def __init__(self):
        # Configure Chroma client based on config settings
        if settings.CHROMA_HOST and settings.CHROMA_PORT:
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT
            )
        else:
            # Persistent or in-memory SQLite storage
            persist_dir = settings.VECTOR_DB_PERSIST_DIR
            if settings.APP_ENV == "testing":
                # Always run in-memory for unit test isolation
                self.client = chromadb.EphemeralClient()
            else:
                os.makedirs(persist_dir, exist_ok=True)
                self.client = chromadb.PersistentClient(path=persist_dir)

        # Retrieve or create collection
        self.collection_name = "kb_documents"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    async def add_document_chunks(
        self, 
        doc_id: str, 
        chunks: List[str], 
        metadata: Dict[str, Any], 
        version: str = "v1"
    ) -> None:
        """
        Embed document chunks and save to ChromaDB.
        """
        if not chunks:
            return
            
        embeddings = await embedding_provider.get_embeddings(chunks)
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        
        # Inject KB version into metadata for filtering
        metadatas = []
        for i in range(len(chunks)):
            meta = metadata.copy()
            meta["version"] = version
            meta["chunk_index"] = i
            meta["doc_id"] = doc_id
            metadatas.append(meta)
            
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=chunks
        )

    async def query_kb(
        self, 
        query: str, 
        version: str = "v1", 
        top_k: int = 3, 
        category_filter: Optional[str] = None
    ) -> List[Citation]:
        """
        Run hybrid search against the knowledge base collection.
        Combines vector similarity with lexical BM25-style matching and a
        lightweight rerank step while preserving version/category filters.
        """
        query_vector = await embedding_provider.get_embedding(query)
        
        where_filter = self._build_where_filter(version, category_filter)
        candidate_k = max(top_k * 4, top_k)

        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=candidate_k,
            where=where_filter
        )

        vector_candidates = self._parse_vector_results(results)
        lexical_candidates = self._lexical_candidates(
            query=query,
            where_filter=where_filter,
            limit=candidate_k
        )

        reranked = self._rerank_candidates(
            query=query,
            vector_candidates=vector_candidates,
            lexical_candidates=lexical_candidates
        )

        citations = []
        for candidate in reranked[:top_k]:
            meta = candidate["metadata"]
            source = meta.get("title", meta.get("doc_id", "Unknown Document"))
            source_label = f"{source} ({meta.get('version', 'v1')})"

            citations.append(Citation(
                source=source_label,
                text=candidate["document"],
                score=round(candidate["score"], 4),
                version=meta.get("version", "v1")
            ))

        return citations

    def _build_where_filter(
        self,
        version: str,
        category_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        if category_filter:
            return {
                "$and": [
                    {"version": version},
                    {"category": category_filter}
                ]
            }
        return {"version": version}

    def _parse_vector_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not results or "documents" not in results or not results["documents"][0]:
            return []

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0] if "distances" in results else [0.0] * len(docs)

        candidates = []
        for doc, meta, dist in zip(docs, metas, distances):
            vector_score = 1.0 - dist if dist is not None else 0.5
            candidates.append({
                "document": doc,
                "metadata": meta or {},
                "vector_score": max(0.0, min(1.0, vector_score)),
                "lexical_score": 0.0
            })

        return candidates

    def _lexical_candidates(
        self,
        query: str,
        where_filter: Dict[str, Any],
        limit: int
    ) -> List[Dict[str, Any]]:
        tokens = self._tokenize(query)
        if not tokens:
            return []

        try:
            records = self.collection.get(
                where=where_filter,
                include=["documents", "metadatas"]
            )
        except Exception:
            return []

        docs = records.get("documents", []) if records else []
        metas = records.get("metadatas", []) if records else []
        if not docs:
            return []

        doc_tokens = [self._tokenize(doc) for doc in docs]
        avg_doc_len = sum(len(items) for items in doc_tokens) / max(len(doc_tokens), 1)
        doc_freq = Counter()
        for items in doc_tokens:
            doc_freq.update(set(items))

        scored = []
        for doc, meta, items in zip(docs, metas, doc_tokens):
            lexical_score = self._bm25_score(tokens, items, doc_freq, len(docs), avg_doc_len)
            if lexical_score <= 0:
                continue
            scored.append({
                "document": doc,
                "metadata": meta or {},
                "vector_score": 0.0,
                "lexical_score": lexical_score
            })

        scored.sort(key=lambda item: item["lexical_score"], reverse=True)
        return scored[:limit]

    def _rerank_candidates(
        self,
        query: str,
        vector_candidates: List[Dict[str, Any]],
        lexical_candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        combined: Dict[str, Dict[str, Any]] = {}
        for candidate in vector_candidates + lexical_candidates:
            key = self._candidate_key(candidate)
            current = combined.setdefault(key, {
                "document": candidate["document"],
                "metadata": candidate["metadata"],
                "vector_score": 0.0,
                "lexical_score": 0.0
            })
            current["vector_score"] = max(current["vector_score"], candidate.get("vector_score", 0.0))
            current["lexical_score"] = max(current["lexical_score"], candidate.get("lexical_score", 0.0))

        if not combined:
            return []

        max_lexical = max(item["lexical_score"] for item in combined.values()) or 1.0
        query_terms = set(self._tokenize(query))
        for item in combined.values():
            lexical_norm = item["lexical_score"] / max_lexical
            exact_overlap = len(query_terms.intersection(self._tokenize(item["document"])))
            overlap_boost = min(0.1, exact_overlap * 0.02)
            item["score"] = min(
                1.0,
                (0.65 * item["vector_score"]) + (0.35 * lexical_norm) + overlap_boost
            )

        return sorted(combined.values(), key=lambda item: item["score"], reverse=True)

    def _candidate_key(self, candidate: Dict[str, Any]) -> str:
        metadata = candidate.get("metadata") or {}
        doc_id = metadata.get("doc_id", "unknown")
        chunk_index = metadata.get("chunk_index", "unknown")
        return f"{doc_id}:{chunk_index}:{candidate.get('document', '')[:80]}"

    def _tokenize(self, text: str) -> List[str]:
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        return [token for token in tokens if token not in STOPWORDS and len(token) > 1]

    def _bm25_score(
        self,
        query_tokens: List[str],
        document_tokens: List[str],
        doc_freq: Counter,
        total_docs: int,
        avg_doc_len: float
    ) -> float:
        if not document_tokens:
            return 0.0

        term_counts = Counter(document_tokens)
        doc_len = len(document_tokens)
        k1 = 1.5
        b = 0.75
        score = 0.0

        for token in query_tokens:
            frequency = term_counts.get(token, 0)
            if frequency == 0:
                continue
            df = doc_freq.get(token, 0)
            idf = math.log(1 + ((total_docs - df + 0.5) / (df + 0.5)))
            denominator = frequency + k1 * (1 - b + b * (doc_len / max(avg_doc_len, 1)))
            score += idf * ((frequency * (k1 + 1)) / denominator)

        return score

    def clear_database(self) -> None:
        """Helper to purge all indexed documents (used in test teardown)."""
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            pass

vector_store = VectorStoreManager()
