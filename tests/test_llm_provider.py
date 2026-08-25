from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import settings
from src.llm.provider import MockLLMProvider, OpenAILLMProvider
from src.rag.embedding import MockEmbeddingProvider, get_embedding_provider


def test_openai_compatible_provider_requires_api_key(monkeypatch):
    monkeypatch.setattr("src.llm.provider.settings.LLM_API_KEY", None)
    monkeypatch.setattr("src.llm.provider.settings.LLM_MODEL_NAME", "chat-model")

    with pytest.raises(ValueError, match="LLM_API_KEY"):
        OpenAILLMProvider()


def test_openai_compatible_provider_requires_model(monkeypatch):
    monkeypatch.setattr("src.llm.provider.settings.LLM_API_KEY", "test-key")
    monkeypatch.setattr("src.llm.provider.settings.LLM_MODEL_NAME", None)

    with pytest.raises(ValueError, match="LLM_MODEL_NAME"):
        OpenAILLMProvider()


def test_openai_compatible_provider_uses_default_sdk_url(monkeypatch):
    monkeypatch.setattr("src.llm.provider.settings.LLM_API_KEY", "test-key")
    monkeypatch.setattr("src.llm.provider.settings.LLM_MODEL_NAME", "chat-model")
    monkeypatch.setattr("src.llm.provider.settings.LLM_BASE_URL", None)

    client = MagicMock()
    with patch("openai.AsyncOpenAI", return_value=client) as client_factory:
        provider = OpenAILLMProvider()

    client_factory.assert_called_once_with(api_key="test-key", base_url=None)
    assert provider.client is client
    assert provider.model == "chat-model"


def test_compatible_chat_does_not_require_openai_embedding_key(monkeypatch):
    monkeypatch.setattr("src.rag.embedding.settings.LLM_PROVIDER", "openai")
    monkeypatch.setattr("src.rag.embedding.settings.OPENAI_API_KEY", None)

    assert isinstance(get_embedding_provider(), MockEmbeddingProvider)


@pytest.mark.asyncio
async def test_mock_provider_follows_current_input_language():
    provider = MockLLMProvider()

    chinese, _, _ = await provider.generate_resolution(
        "Support ticket", "我要申请退款", "policy"
    )
    english, _, _ = await provider.generate_resolution(
        "客服工单", "Please help with my refund", "policy"
    )
    switched, _, _ = await provider.generate_resolution(
        "客服工单", "请用英文回复退款流程", "policy"
    )

    assert "感谢" in chinese
    assert "Thank you" in english
    assert "Thank you" in switched


@pytest.mark.asyncio
async def test_openai_compatible_prompts_define_response_language_policy(monkeypatch):
    monkeypatch.setattr("src.llm.provider.settings.LLM_API_KEY", "test-key")
    monkeypatch.setattr("src.llm.provider.settings.LLM_MODEL_NAME", "chat-model")
    monkeypatch.setattr("src.llm.provider.settings.LLM_BASE_URL", None)

    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(content="ok"))]
    completion.usage = MagicMock(prompt_tokens=10, completion_tokens=2)
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=completion)

    with patch("openai.AsyncOpenAI", return_value=client):
        provider = OpenAILLMProvider()

    await provider.generate_resolution("English subject", "我要查询物流", "English context")
    resolution_call = client.chat.completions.create.await_args
    resolution_messages = resolution_call.kwargs["messages"]
    assert resolution_call.kwargs["max_tokens"] == settings.LLM_RESOLVER_MAX_TOKENS
    assert "current Description" in resolution_messages[0]["content"]
    assert (
        "explicitly asks for a different response language"
        in resolution_messages[0]["content"]
    )

    await provider.run_chat(
        [
            {"role": "user", "content": "Please reply in English"},
            {"role": "assistant", "content": "Previous response"},
            {"role": "user", "content": "现在物流到哪里了？"},
        ],
        "English context",
    )
    chat_messages = client.chat.completions.create.await_args.kwargs["messages"]
    assert "latest user message" in chat_messages[0]["content"]
    assert "Do not preserve a previous response language" in chat_messages[0]["content"]


@pytest.mark.asyncio
async def test_qa_uses_compact_schema_limits_and_optional_fast_model(monkeypatch):
    monkeypatch.setattr("src.llm.provider.settings.LLM_API_KEY", "test-key")
    monkeypatch.setattr("src.llm.provider.settings.LLM_MODEL_NAME", "main-model")
    monkeypatch.setattr("src.llm.provider.settings.LLM_QA_MODEL_NAME", "fast-judge")

    completion = MagicMock()
    completion.choices = [
        MagicMock(
            message=MagicMock(
                content='{"score":0.9,"hallucination_detected":false,'
                '"citation_verified":true}'
            )
        )
    ]
    completion.usage = MagicMock(prompt_tokens=120, completion_tokens=20)
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=completion)

    with patch("openai.AsyncOpenAI", return_value=client):
        provider = OpenAILLMProvider()

    result, _, _ = await provider.evaluate_qa("question", ["evidence"], "answer")
    call = client.chat.completions.create.await_args

    assert result["score"] == 0.9
    assert call.kwargs["model"] == "fast-judge"
    assert call.kwargs["max_tokens"] == settings.LLM_QA_MAX_TOKENS
    assert "reasons" not in call.kwargs["messages"][1]["content"]
