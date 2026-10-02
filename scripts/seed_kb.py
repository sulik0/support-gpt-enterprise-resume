import os
import sys
import asyncio
import argparse

# Ensure project root is in path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database import init_db, AsyncSessionLocal
from src.rag.kb_versioning import kb_versioning_service
from src.rag.demo_documents import DEMO_DOCUMENTS

SEED_DOCUMENTS = [
    {
        "doc_id": "refund_policy_v1",
        "title": "Corporate Refund Policy",
        "category": "billing",
        "version": "v1",
        "content": (
            "All billing refund requests must be filed within 30 days of the initial subscription payment. "
            "Refunds are only eligible for accounts with no active disputes. Approved refunds will reflect "
            "in the customer's bank statement within 3 to 5 business days."
        ),
        "metadata": {"source": "Finance Department", "doc_type": "policy"}
    },
    {
        "doc_id": "refund_policy_v2",
        "title": "Corporate Refund Policy V2",
        "category": "billing",
        "version": "v2",
        "content": (
            "Our corporate refund policy V2 allows refund requests to be filed up to 60 days from purchase. "
            "A 5% processing fee is deducted from all V2 refund requests. Refunds are sent to the original payment card "
            "and take 3-5 business days to clear."
        ),
        "metadata": {"source": "Finance Department v2", "doc_type": "policy"}
    },
    {
        "doc_id": "system_outage_guide",
        "title": "API Outage Remediation Steps",
        "category": "technical",
        "version": "v1",
        "content": (
            "In case of API server connectivity timeouts or 504 Gateway errors, technical support agents must "
            "verify the backup routing cluster. DevOps patches are deployed to point to fallback API clusters in the "
            "AWS us-east-1 region. Clear client caches once routing switches to restore service."
        ),
        "metadata": {"source": "DevOps Team", "doc_type": "technical_guide"}
    },
    {
        "doc_id": "account_setup_preferences",
        "title": "User Account Profile Settings",
        "category": "general",
        "version": "v1",
        "content": (
            "To configure your customer account preferences, navigate to Settings -> Preferences -> Profile "
            "and update your verification email address. Click the validation link sent to your inbox to enable "
            "API keys access."
        ),
        "metadata": {"source": "Product Management", "doc_type": "user_guide"}
    }
]

async def seed(only_missing: bool = False):
    """导入演示文档；增量模式保留后台已经维护的同名内容。"""
    print("Initializing database tables...")
    await init_db()
    
    async with AsyncSessionLocal() as db:
        print("Registering and indexing seed documents...")
        for doc in [*SEED_DOCUMENTS, *DEMO_DOCUMENTS]:
            if only_missing and await kb_versioning_service.get_document(db, doc["doc_id"]):
                print(f"Skipping existing document: {doc['doc_id']}")
                continue
            print(f"Adding: {doc['title']} ({doc['version']})")
            await kb_versioning_service.register_document(
                db=db,
                doc_id=doc["doc_id"],
                title=doc["title"],
                content=doc["content"],
                category=doc["category"],
                version=doc["version"],
                metadata=doc["metadata"]
            )
            
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导入 SupportGPT 演示知识库")
    parser.add_argument("--only-missing", action="store_true", help="只添加不存在的文档，保留后台编辑内容")
    args = parser.parse_args()
    asyncio.run(seed(only_missing=args.only_missing))
