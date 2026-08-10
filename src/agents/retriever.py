import time
import logging
from typing import Dict, Any

from src.rag.vector_store import vector_store
from src.observability.metrics import AGENT_EXECUTION_DURATION_SECONDS
from src.observability.tracing import get_tracer, set_span_attributes
from src.observability.langsmith_tracing import traceable

logger = logging.getLogger("supportgpt.agents.retriever")
tracer = get_tracer(__name__)


class KnowledgeRetrievalAgent:
    """
    Retrieves supporting context, documentation guides, policies, and FAQs
    from the vector database.
    """

    @traceable(name="supportgpt.rag.hybrid_retriever", run_type="retriever")
    async def retrieve(self, state: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"Retriever Node started for version: {state.get('kb_version')}")

        if "Security threat" in "".join(state.get("errors", [])):
            # Bypass node if security threats are already detected
            return state

        subject = state.get("subject", "")
        description = state.get("description", "")
        kb_version = state.get("kb_version", "v1")
        category_filter = state.get(
            "department"
        )  # Can align filters with detected department

        # Use a unified query string
        query_str = f"{subject} {description}"

        try:
            # Run semantic query on our ChromaDB manager
            with tracer.start_as_current_span("rag.query") as span:
                set_span_attributes(
                    span,
                    {
                        "ticket.id": state.get("ticket_id"),
                        "customer.id": state.get("customer_id"),
                        "kb.version": kb_version,
                        "rag.category_filter": category_filter,
                        "rag.query_length": len(query_str),
                        "rag.top_k": 3,
                    },
                )
                citations = await vector_store.query_kb(
                    query=query_str,
                    version=kb_version,
                    top_k=3,
                    category_filter=(
                        category_filter if category_filter != "general" else None
                    ),
                )
                set_span_attributes(span, {"rag.citation_count": len(citations)})

            # Fallback query without category filter if no documents found
            if not citations and category_filter != "general":
                logger.info("Retrying query without category filter...")
                with tracer.start_as_current_span("rag.query_fallback") as span:
                    set_span_attributes(
                        span,
                        {
                            "ticket.id": state.get("ticket_id"),
                            "kb.version": kb_version,
                            "rag.original_category_filter": category_filter,
                            "rag.top_k": 3,
                        },
                    )
                    citations = await vector_store.query_kb(
                        query=query_str, version=kb_version, top_k=3
                    )
                    set_span_attributes(span, {"rag.citation_count": len(citations)})

            duration = time.time() - start_time
            AGENT_EXECUTION_DURATION_SECONDS.record(
                duration, {"agent_name": "knowledge_retriever"}
            )

            return {**state, "context_citations": citations}

        except Exception as e:
            logger.error(f"Error querying vector store in retriever: {e}")
            return {
                **state,
                "errors": state.get("errors", [])
                + [f"Retriever agent error: {str(e)}"],
                "context_citations": [],
            }


knowledge_retriever_agent = KnowledgeRetrievalAgent()
