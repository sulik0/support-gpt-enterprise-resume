import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.db_models import KnowledgeDoc
from src.rag.vector_store import vector_store
from src.rag.chunking import RecursiveTextSplitter

logger = logging.getLogger("supportgpt.rag.kb_versioning")

class KBVersioningService:
    """负责知识文档的版本登记、切分和向量索引同步。

    SQL 保存文档元数据，ChromaDB 保存对应版本的检索向量。
    """
    def __init__(self):
        self.splitter = RecursiveTextSplitter()

    async def register_document(
        self, 
        db: AsyncSession, 
        doc_id: str, 
        title: str, 
        content: str, 
        category: str, 
        version: str = "v1", 
        metadata: Dict[str, Any] = None
    ) -> KnowledgeDoc:
        """
        Save a document description to the database and chunk/index it in ChromaDB.
        """
        # Save to PostgreSQL / database
        doc = KnowledgeDoc(
            id=doc_id,
            title=title,
            content=content,
            category=category,
            version=version,
            metadata_json=metadata or {}
        )
        
        # Merge to support upsert behavior
        await db.merge(doc)
        await db.commit()

        # Chunk text and add to Vector DB
        chunks = self.splitter.split_text(content)
        meta = {
            "title": title,
            "category": category,
            "doc_id": doc_id
        }
        if metadata:
            meta.update(metadata)
            
        await vector_store.add_document_chunks(
            doc_id=doc_id,
            chunks=chunks,
            metadata=meta,
            version=version
        )
        
        logger.info(f"Registered document {doc_id} under version {version} successfully.")
        return doc

    async def get_active_versions(self, db: AsyncSession) -> List[str]:
        """List all unique KB versions currently stored in the system."""
        result = await db.execute(select(KnowledgeDoc.version).distinct())
        versions = [row[0] for row in result.all()]
        return sorted(versions) if versions else ["v1"]

    async def delete_version(self, db: AsyncSession, version: str) -> None:
        """
        Purge an entire KB version from both PostgreSQL database records 
        and ChromaDB index files.
        """
        # 1. Delete from SQLite/PostgreSQL
        result = await db.execute(select(KnowledgeDoc).filter(KnowledgeDoc.version == version))
        docs = result.scalars().all()
        for doc in docs:
            await db.delete(doc)
        await db.commit()

        # 2. Delete from ChromaDB
        try:
            vector_store.collection.delete(where={"version": version})
            logger.info(f"Purged KB version {version} from databases successfully.")
        except Exception as e:
            logger.error(f"Failed to delete version {version} from vector store: {e}")

    async def clone_version(self, db: AsyncSession, source_version: str, target_version: str) -> None:
        """
        Clone all documents from a source version to a target version.
        Useful for branching (e.g., seeding v2 content based on v1 data).
        """
        result = await db.execute(select(KnowledgeDoc).filter(KnowledgeDoc.version == source_version))
        source_docs = result.scalars().all()
        
        for doc in source_docs:
            await self.register_document(
                db=db,
                doc_id=f"{doc.id}_clone",
                title=doc.title,
                content=doc.content,
                category=doc.category,
                version=target_version,
                metadata=doc.metadata_json
            )
        logger.info(f"Successfully cloned version {source_version} into version {target_version}")

kb_versioning_service = KBVersioningService()
