import hashlib
import math
from typing import Protocol

import httpx

from backend.app.core.config import Settings
from backend.app.retrieval.text import terms


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Offline bag-of-token feature hashing, not a learned semantic embedding model."""
    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for term in terms(text):
                index = int.from_bytes(hashlib.sha256(term.encode()).digest()[:8], "big") % self.dimensions
                vector[index] += 1.0
            length = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / length for value in vector])
        return vectors


class OpenAIEmbedder:
    def __init__(self, settings: Settings):
        self.settings = settings

    def embed(self, texts: list[str]) -> list[list[float]]:
        key = self.settings.embedding_api_key or self.settings.llm_api_key
        assert key is not None
        payload = {"model": self.settings.embedding_model, "input": texts}
        # Configure dimensions to the actual returned model width; not all compatible endpoints
        # accept the OpenAI-specific dimensions request field.
        with httpx.Client(timeout=self.settings.provider_timeout_seconds) as client:
            response = client.post(
                self.settings.embedding_base_url.rstrip("/") + "/embeddings",
                headers={"Authorization": "Bearer " + key.get_secret_value()}, json=payload,
            )
            response.raise_for_status()
            values = sorted(response.json()["data"], key=lambda row: row["index"])
        return [row["embedding"] for row in values]


class SentenceTransformerEmbedder:
    def __init__(self, settings: Settings):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install the local-embeddings extra to use sentence-transformers") from exc
        self.model = SentenceTransformer(settings.embedding_model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()


def create_embedder(settings: Settings) -> Embedder:
    if settings.embedding_provider == "openai":
        return OpenAIEmbedder(settings)
    if settings.embedding_provider == "sentence_transformer":
        return SentenceTransformerEmbedder(settings)
    return HashEmbedder(settings.embedding_dimensions)
