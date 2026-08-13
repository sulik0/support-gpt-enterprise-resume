import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple
from src.config import settings
from src.observability.tracing import trace_operation


class BaseLLMProvider(ABC):
    """定义工单分析、回复生成、QA 和对话能力的统一接口。"""

    @abstractmethod
    async def analyze_ticket(self, text: str) -> Tuple[Dict[str, Any], int, int]:
        """
        Analyze sentiment, priority, intent, and department.
        Returns: (analysis_dict, input_tokens, output_tokens)
        """
        pass

    @abstractmethod
    async def generate_resolution(
        self, subject: str, description: str, context: str
    ) -> Tuple[str, int, int]:
        """
        Generate response text based on document context.
        Returns: (response_text, input_tokens, output_tokens)
        """
        pass

    @abstractmethod
    async def evaluate_qa(
        self, query: str, context: List[str], response: str
    ) -> Tuple[Dict[str, Any], int, int]:
        """
        Perform hallucination detection and response quality scoring.
        Returns: (qa_evaluation_dict, input_tokens, output_tokens)
        """
        pass

    @abstractmethod
    async def run_chat(
        self, history: List[Dict[str, str]], context: str
    ) -> Tuple[str, int, int]:
        """
        Run generic conversational completion.
        Returns: (completion, input_tokens, output_tokens)
        """
        pass


class MockLLMProvider(BaseLLMProvider):
    """提供无需外部凭据的确定性 Mock LLM，便于本地演示与测试。"""

    @trace_operation(name="supportgpt.llm.analyze_ticket", component="llm")
    async def analyze_ticket(self, text: str) -> Tuple[Dict[str, Any], int, int]:
        text_lower = text.lower()
        sentiment = "neutral"
        priority = "medium"
        department = "general"
        detected_emotions = ["calm"]
        intent = "information_request"

        if any(
            x in text_lower
            for x in ["refund", "billing", "charge", "invoice", "payment", "card"]
        ):
            sentiment = "negative"
            priority = "high"
            department = "billing"
            detected_emotions = ["frustrated", "annoyed"]
            intent = "billing_dispute"
        elif any(
            x in text_lower
            for x in ["down", "crash", "error", "bug", "broken", "offline", "slow"]
        ):
            sentiment = "negative"
            priority = "urgent"
            department = "technical"
            detected_emotions = ["anxious", "frustrated"]
            intent = "outage_report"
        elif "thank" in text_lower or "great" in text_lower or "love" in text_lower:
            sentiment = "positive"
            priority = "low"
            detected_emotions = ["happy", "grateful"]
            intent = "feedback"

        analysis = {
            "sentiment": sentiment,
            "priority": priority,
            "department": department,
            "intent": intent,
            "detected_emotions": detected_emotions,
            "confidence_score": 0.95,
        }
        return analysis, 150, 45

    @trace_operation(name="supportgpt.llm.generate_resolution", component="llm")
    async def generate_resolution(
        self, subject: str, description: str, context: str
    ) -> Tuple[str, int, int]:
        desc_lower = description.lower()
        if "billing" in desc_lower or "refund" in desc_lower:
            response = (
                "Thank you for reaching out regarding your billing issue. According to our refund policy: "
                "refund requests must be submitted within 30 days of purchase. I have initiated the refund "
                "approval process for your transaction, and it should reflect in your account within 3-5 business days."
            )
        elif "down" in desc_lower or "crash" in desc_lower or "error" in desc_lower:
            response = (
                "I apologize for the service disruption. Based on our system status and the technical documentation: "
                "we had a minor outage in our API server layer. Our DevOps team has deployed a patch, and "
                "services are now fully operational. Please clear your cache and try again. Let me know if you still see errors."
            )
        else:
            response = (
                "Thank you for contacting customer support. I have retrieved our product guides: "
                "To configure your account, please head to Settings -> Preferences, and verify your email. "
                "Let me know if you need any additional help!"
            )

        return response, 250, 80

    @trace_operation(name="supportgpt.llm.evaluate_qa", component="llm")
    async def evaluate_qa(
        self, query: str, context: List[str], response: str
    ) -> Tuple[Dict[str, Any], int, int]:
        # Simple heuristics for mock QA:
        # If response mentions policy and context has policy, high score.
        qa_score = 0.92
        hallucination_detected = False
        reasons = ["Response matches facts retrieved from context."]

        if len(context) == 0:
            qa_score = 0.45
            hallucination_detected = True
            reasons = [
                "No retrieval context was provided, leading to potential hallucination."
            ]

        evaluation = {
            "qa_score": qa_score,
            "hallucination_detected": hallucination_detected,
            "reasons": reasons,
            "faithfulness": qa_score,
            "context_precision": 0.90 if len(context) > 0 else 0.0,
            "citation_verified": True,
        }
        return evaluation, 350, 60

    @trace_operation(name="supportgpt.llm.run_chat", component="llm")
    async def run_chat(
        self, history: List[Dict[str, str]], context: str
    ) -> Tuple[str, int, int]:
        last_message = history[-1]["content"] if history else ""
        response = f"This is an automated response from SupportGPT. I received your message: '{last_message}'. How else can I assist you today?"
        return response, 200, 40


class OpenAILLMProvider(BaseLLMProvider):
    """通过 OpenAI-compatible Chat Completions 提供统一 LLM 能力。

    可连接 OpenAI、DeepSeek、Qwen、vLLM 等兼容服务。
    """

    def __init__(self):
        from openai import AsyncOpenAI

        if not settings.LLM_API_KEY:
            raise ValueError("LLM_PROVIDER=openai 时必须配置 LLM_API_KEY")
        if not settings.LLM_MODEL_NAME:
            raise ValueError("LLM_PROVIDER=openai 时必须配置 LLM_MODEL_NAME")

        # base_url 为空时使用 OpenAI SDK 默认地址，配置后可连接兼容服务。
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL or None,
        )
        self.model = settings.LLM_MODEL_NAME

    async def _call_gpt(
        self, messages: List[Dict[str, str]], json_mode: bool = False
    ) -> Tuple[str, int, int]:
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=0.0, **kwargs
        )
        content = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        return content, input_tokens, output_tokens

    @trace_operation(name="supportgpt.llm.analyze_ticket", component="llm")
    async def analyze_ticket(self, text: str) -> Tuple[Dict[str, Any], int, int]:
        prompt = (
            "Analyze the following support ticket and return a JSON object with: "
            "sentiment (positive, neutral, negative), priority (low, medium, high, urgent), "
            "department (billing, technical, shipping, general), intent (short description), "
            "detected_emotions (list of strings), and confidence_score (float 0 to 1).\n\n"
            f"Ticket Content: {text}"
        )
        messages = [
            {
                "role": "system",
                "content": "You are an expert customer service ticket analyzer. Always output JSON.",
            },
            {"role": "user", "content": prompt},
        ]
        content, in_tok, out_tok = await self._call_gpt(messages, json_mode=True)
        return json.loads(content), in_tok, out_tok

    @trace_operation(name="supportgpt.llm.generate_resolution", component="llm")
    async def generate_resolution(
        self, subject: str, description: str, context: str
    ) -> Tuple[str, int, int]:
        prompt = (
            f"Subject: {subject}\n"
            f"Description: {description}\n\n"
            f"Retrieved Context:\n{context}\n\n"
            "Generate a professional response to the customer. Ensure you cite your sources where appropriate."
        )
        messages = [
            {
                "role": "system",
                "content": "You are a customer support agent. Address the issue using only the provided context. If the context doesn't have the answer, state that you need to escalate.",
            },
            {"role": "user", "content": prompt},
        ]
        return await self._call_gpt(messages, json_mode=False)

    @trace_operation(name="supportgpt.llm.evaluate_qa", component="llm")
    async def evaluate_qa(
        self, query: str, context: List[str], response: str
    ) -> Tuple[Dict[str, Any], int, int]:
        prompt = (
            f"Query: {query}\n"
            f"Context: {json.dumps(context)}\n"
            f"Response: {response}\n\n"
            "Evaluate this response for hallucination and quality. Output a JSON object with:\n"
            "qa_score (0.0 to 1.0),\n"
            "hallucination_detected (boolean),\n"
            "reasons (list of strings),\n"
            "faithfulness (0.0 to 1.0),\n"
            "context_precision (0.0 to 1.0),\n"
            "citation_verified (boolean)"
        )
        messages = [
            {
                "role": "system",
                "content": "You are an AI quality assurance agent verifying customer support answers. Output JSON only.",
            },
            {"role": "user", "content": prompt},
        ]
        content, in_tok, out_tok = await self._call_gpt(messages, json_mode=True)
        return json.loads(content), in_tok, out_tok

    @trace_operation(name="supportgpt.llm.run_chat", component="llm")
    async def run_chat(
        self, history: List[Dict[str, str]], context: str
    ) -> Tuple[str, int, int]:
        system_msg = "You are SupportGPT, a customer support AI assistant. Answer using the retrieved context if available."
        if context:
            system_msg += f"\n\nContext:\n{context}"

        messages = [{"role": "system", "content": system_msg}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        return await self._call_gpt(messages, json_mode=False)


class AzureOpenAILLMProvider(BaseLLMProvider):
    """通过 Azure OpenAI 部署实现统一 LLM Provider 接口。"""

    def __init__(self):
        from openai import AsyncAzureOpenAI

        self.client = AsyncAzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT

    async def _call_gpt(
        self, messages: List[Dict[str, str]], json_mode: bool = False
    ) -> Tuple[str, int, int]:
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(
            model=self.deployment, messages=messages, temperature=0.0, **kwargs
        )
        content = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        return content, input_tokens, output_tokens

    @trace_operation(name="supportgpt.llm.analyze_ticket", component="llm")
    async def analyze_ticket(self, text: str) -> Tuple[Dict[str, Any], int, int]:
        prompt = (
            "Analyze the following support ticket and return a JSON object with: "
            "sentiment (positive, neutral, negative), priority (low, medium, high, urgent), "
            "department (billing, technical, shipping, general), intent (short description), "
            "detected_emotions (list of strings), and confidence_score (float 0 to 1).\n\n"
            f"Ticket Content: {text}"
        )
        messages = [
            {
                "role": "system",
                "content": "You are an expert customer service ticket analyzer. Always output JSON.",
            },
            {"role": "user", "content": prompt},
        ]
        content, in_tok, out_tok = await self._call_gpt(messages, json_mode=True)
        return json.loads(content), in_tok, out_tok

    @trace_operation(name="supportgpt.llm.generate_resolution", component="llm")
    async def generate_resolution(
        self, subject: str, description: str, context: str
    ) -> Tuple[str, int, int]:
        prompt = (
            f"Subject: {subject}\n"
            f"Description: {description}\n\n"
            f"Retrieved Context:\n{context}\n\n"
            "Generate a professional response to the customer. Ensure you cite your sources where appropriate."
        )
        messages = [
            {
                "role": "system",
                "content": "You are a customer support agent. Address the issue using only the provided context. If the context doesn't have the answer, state that you need to escalate.",
            },
            {"role": "user", "content": prompt},
        ]
        return await self._call_gpt(messages, json_mode=False)

    @trace_operation(name="supportgpt.llm.evaluate_qa", component="llm")
    async def evaluate_qa(
        self, query: str, context: List[str], response: str
    ) -> Tuple[Dict[str, Any], int, int]:
        prompt = (
            f"Query: {query}\n"
            f"Context: {json.dumps(context)}\n"
            f"Response: {response}\n\n"
            "Evaluate this response for hallucination and quality. Output a JSON object with:\n"
            "qa_score (0.0 to 1.0),\n"
            "hallucination_detected (boolean),\n"
            "reasons (list of strings),\n"
            "faithfulness (0.0 to 1.0),\n"
            "context_precision (0.0 to 1.0),\n"
            "citation_verified (boolean)"
        )
        messages = [
            {
                "role": "system",
                "content": "You are an AI quality assurance agent verifying customer support answers. Output JSON only.",
            },
            {"role": "user", "content": prompt},
        ]
        content, in_tok, out_tok = await self._call_gpt(messages, json_mode=True)
        return json.loads(content), in_tok, out_tok

    @trace_operation(name="supportgpt.llm.run_chat", component="llm")
    async def run_chat(
        self, history: List[Dict[str, str]], context: str
    ) -> Tuple[str, int, int]:
        system_msg = "You are SupportGPT, a customer support AI assistant. Answer using the retrieved context if available."
        if context:
            system_msg += f"\n\nContext:\n{context}"

        messages = [{"role": "system", "content": system_msg}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        return await self._call_gpt(messages, json_mode=False)


# Provider factory
def get_llm_provider() -> BaseLLMProvider:
    provider_type = settings.LLM_PROVIDER.lower()
    if provider_type == "openai":
        return OpenAILLMProvider()
    elif provider_type == "azure":
        return AzureOpenAILLMProvider()
    else:
        return MockLLMProvider()


llm_provider = get_llm_provider()
