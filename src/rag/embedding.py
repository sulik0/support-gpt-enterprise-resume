import math
import random
from abc import ABC, abstractmethod
from typing import List
from src.config import settings

class BaseEmbeddingProvider(ABC):
    """定义单条和批量文本向量化的统一接口。"""

    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for a single text string."""
        pass

    @abstractmethod
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate vector embeddings for a list of text strings."""
        pass


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """生成稳定的本地 Mock 向量，支持无外部模型运行。"""

    def _generate_mock_vector(self, text: str) -> List[float]:
        # Generate stable mock vector based on text hash
        val = hash(text)
        random.seed(val)
        vector = [random.uniform(-1, 1) for _ in range(1536)]
        # Normalize vector to unit length
        norm = math.sqrt(sum(x*x for x in vector))
        return [x / norm for x in vector]

    async def get_embedding(self, text: str) -> List[float]:
        return self._generate_mock_vector(text)

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self._generate_mock_vector(t) for t in texts]


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """调用 OpenAI Embedding API 生成文本向量。"""

    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "text-embedding-3-small"

    async def get_embedding(self, text: str) -> List[float]:
        response = await self.client.embeddings.create(
            input=[text],
            model=self.model
        )
        return response.data[0].embedding

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        response = await self.client.embeddings.create(
            input=texts,
            model=self.model
        )
        return [item.embedding for item in response.data]


def get_embedding_provider() -> BaseEmbeddingProvider:
    provider_type = settings.LLM_PROVIDER.lower()
    if provider_type in ["openai", "azure"]:
        # Standard OpenAI embedding provider
        return OpenAIEmbeddingProvider()
    return MockEmbeddingProvider()

embedding_provider = get_embedding_provider()
