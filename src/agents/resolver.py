import json
import time
import logging
from typing import Dict, Any

from src.config import settings
from src.llm.provider import llm_provider
from src.observability.metrics import AGENT_EXECUTION_DURATION_SECONDS

logger = logging.getLogger("supportgpt.agents.resolver")


class ResolutionAgent:
    """负责结合工单、Tool Context 和知识库引用生成回复草稿。

    该节点只生成建议回复，不直接执行高风险业务操作。
    """

    async def resolve(self, state: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"Resolver Node started for ticket_id: {state.get('ticket_id')}")

        if "Security threat" in "".join(state.get("errors", [])):
            return state

        subject = state.get("subject", "")
        description = state.get("description", "")
        citations = state.get("context_citations", [])
        tool_context = state.get("tool_context", {})

        # 只向模型提供 Top RAG 证据和必要业务字段。
        kb_context = self._compact_rag_context(citations)
        business_context = self._compact_tool_context(tool_context)
        combined_context = (
            f"KB evidence:\n{kb_context}\n\nBusiness facts:\n{business_context}"
        )

        try:
            # Generate the text from LLM provider
            response_text, in_tok, out_tok = await llm_provider.generate_resolution(
                subject=subject, description=description, context=combined_context
            )

            # Update metrics
            state["tokens_input"] = state.get("tokens_input", 0) + in_tok
            state["tokens_output"] = state.get("tokens_output", 0) + out_tok

            duration = time.time() - start_time
            AGENT_EXECUTION_DURATION_SECONDS.record(
                duration, {"agent_name": "resolution_agent"}
            )

            return {**state, "suggested_response": response_text}

        except Exception as e:
            logger.error(f"Error formulating resolution in resolver: {e}")
            return {
                **state,
                "errors": state.get("errors", []) + [f"Resolver agent error: {str(e)}"],
                "suggested_response": "I apologize, but I encountered an error while writing a resolution. Please escalate to a support manager.",
            }

    @staticmethod
    def _compact_rag_context(citations: list[Any]) -> str:
        """限制 RAG 文档数量和总字符数，保留 citation 来源。"""
        remaining = settings.LLM_RESOLVER_MAX_RAG_CHARS
        blocks = []
        for index, citation in enumerate(citations[:2], start=1):
            source = str(getattr(citation, "source", f"doc-{index}"))
            text = str(getattr(citation, "text", ""))
            prefix = f"[S{index}] {source}: "
            available = max(remaining - len(prefix), 0)
            if available <= 0:
                break
            block = prefix + text[:available]
            blocks.append(block)
            remaining -= len(block)
        return "\n".join(blocks) if blocks else "No relevant KB evidence."

    @staticmethod
    def _compact_tool_context(tool_context: Dict[str, Any]) -> str:
        """移除 Tool 审计等生成阶段无需字段。"""
        if not tool_context:
            return "No relevant business facts."
        profile = tool_context.get("customer_profile") or {}
        compact = {
            "customer": {
                "tier": profile.get("tier"),
                "open_tickets_count": profile.get("open_tickets_count"),
            },
            "recent_orders": [
                {
                    key: order.get(key)
                    for key in ("order_id", "status", "items", "order_date")
                    if order.get(key) is not None
                }
                for order in (tool_context.get("recent_orders") or [])[:2]
            ],
            "past_tickets": [
                {
                    key: ticket.get(key)
                    for key in ("subject", "status", "resolution")
                    if ticket.get(key) is not None
                }
                for ticket in (tool_context.get("past_tickets") or [])[:2]
            ],
        }
        content = json.dumps(compact, default=str, ensure_ascii=False, separators=(",", ":"))
        return content[: settings.LLM_RESOLVER_MAX_TOOL_CHARS]


resolution_agent = ResolutionAgent()
