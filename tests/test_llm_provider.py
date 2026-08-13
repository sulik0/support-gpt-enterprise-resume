from unittest.mock import MagicMock, patch

import pytest

from src.llm.provider import OpenAILLMProvider
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
