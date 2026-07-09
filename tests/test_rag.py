import pytest
import os
from src.rag.chunking import RecursiveTextSplitter
from src.rag.embedding import MockEmbeddingProvider
from src.rag.vector_store import vector_store
from src.rag.ingestion import extract_text_from_file

def test_recursive_text_splitter():
    text = "Paragraph one is short.\n\nParagraph two contains some details. Let us check sentence division boundaries. Paragraph three."
    splitter = RecursiveTextSplitter(chunk_size=50, chunk_overlap=10)
    chunks = splitter.split_text(text)
    
    assert len(chunks) > 0
    for c in chunks:
        assert len(c) <= 50
        assert len(c.strip()) > 0

@pytest.mark.asyncio
async def test_mock_embeddings():
    provider = MockEmbeddingProvider()
    text = "hello supportgpt"
    vec = await provider.get_embedding(text)
    
    assert len(vec) == 1536
    # Check unit vector property (sum of squares ~ 1)
    sq_sum = sum(x*x for x in vec)
    assert abs(sq_sum - 1.0) < 1e-5

@pytest.mark.asyncio
async def test_vector_store_operations():
    # EPHEMERAL client should be active during tests
    assert vector_store.collection_name == "kb_documents"
    
    doc_id = "test_doc_01"
    chunks = [
        "First chunk describes user account registration setups.",
        "Second chunk details refund request windows of 30 days."
    ]
    metadata = {"title": "Test Guide Document", "category": "general"}
    
    # Add documents
    await vector_store.add_document_chunks(doc_id, chunks, metadata, version="v1")
    
    # Query matching v1
    results = await vector_store.query_kb("refund request", version="v1", top_k=2)
    assert any("refund" in r.text.lower() for r in results)
    assert results[0].version == "v1"
    
    # Query matching wrong version v2 should return empty
    empty_results = await vector_store.query_kb("refund request", version="v2", top_k=2)
    assert len(empty_results) == 0

@pytest.mark.asyncio
async def test_hybrid_search_prioritizes_keyword_matches():
    chunks = [
        "Warranty claims for damaged headphones require a serial number and proof of purchase.",
        "Account profile updates can be completed from the customer settings page."
    ]
    metadata = {"title": "Support Policy", "category": "general"}

    await vector_store.add_document_chunks(
        "hybrid_policy",
        chunks,
        metadata,
        version="v1"
    )

    results = await vector_store.query_kb(
        "damaged headphones warranty serial number",
        version="v1",
        top_k=1
    )

    assert len(results) == 1
    assert "warranty" in results[0].text.lower()
    assert "serial number" in results[0].text.lower()
    assert results[0].score > 0

def test_ingestion_text_fallback(tmp_path):
    # Test simple text extraction from txt/md files
    file_path = tmp_path / "sample.txt"
    content = "Hello testing file ingestion capabilities."
    file_path.write_text(content, encoding="utf-8")
    
    extracted = extract_text_from_file(str(file_path))
    assert extracted == content
