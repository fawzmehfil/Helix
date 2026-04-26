"""Embedding providers for semantic reuse."""

from __future__ import annotations

import hashlib
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Protocol


class EmbeddingProvider(Protocol):
    """Provider contract for semantic-reuse embeddings."""

    model_id: str

    def embed(self, text: str) -> list[float]:
        """Return an embedding vector for text."""
        ...


@dataclass
class EmbeddingResult:
    """Embedding vector plus measurement metadata."""

    vector: list[float]
    latency_ms: float
    calls: int


class HashEmbeddingProvider:
    """Deterministic local fallback based on hashed character n-grams."""

    model_id = "local-hash-embedding"

    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        lowered = re.sub(r"\b(corporation|company|inc)\b", "corp", text.lower())
        lowered = f"  {lowered}  "
        ngrams = [lowered[index : index + 3] for index in range(max(1, len(lowered) - 2))]
        for ngram in ngrams:
            digest = hashlib.sha256(ngram.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return normalize_vector(vector)


class SentenceTransformerEmbeddingProvider:
    """Optional local sentence-transformers provider."""

    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self.model_id = model
        self._model = SentenceTransformer(model)

    def embed(self, text: str) -> list[float]:
        vector = self._model.encode(text, normalize_embeddings=True)
        return [float(value) for value in vector]


class OpenAIEmbeddingProvider:
    """OpenAI embeddings provider."""

    def __init__(self, model: str = "text-embedding-3-small", api_key: str | None = None) -> None:
        self.model_id = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def embed(self, text: str) -> list[float]:
        import openai

        client = openai.OpenAI(api_key=self.api_key)
        result = client.embeddings.create(model=self.model_id, input=text)
        return [float(value) for value in result.data[0].embedding]


class CachedEmbeddingProvider:
    """In-memory cache around an embedding provider."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider
        self.model_id = provider.model_id
        self._cache: dict[str, list[float]] = {}
        self.last_latency_ms = 0.0
        self.last_calls = 0

    def embed_measured(self, text: str) -> EmbeddingResult:
        if text in self._cache:
            self.last_latency_ms = 0.0
            self.last_calls = 0
            return EmbeddingResult(self._cache[text], 0.0, 0)
        started = time.perf_counter()
        vector = self.provider.embed(text)
        elapsed = (time.perf_counter() - started) * 1000
        self._cache[text] = vector
        self.last_latency_ms = elapsed
        self.last_calls = 1
        return EmbeddingResult(vector, elapsed, 1)

    def embed(self, text: str) -> list[float]:
        return self.embed_measured(text).vector


def normalize_vector(vector: list[float]) -> list[float]:
    """Return a unit vector."""
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return cosine similarity for normalized or unnormalized vectors."""
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def build_embedding_provider(backend: str = "local", model: str | None = None) -> CachedEmbeddingProvider:
    """Build configured embedding provider with safe local fallback."""
    if backend == "openai":
        return CachedEmbeddingProvider(OpenAIEmbeddingProvider(model or "text-embedding-3-small"))
    if backend == "local":
        try:
            return CachedEmbeddingProvider(SentenceTransformerEmbeddingProvider(model or "all-MiniLM-L6-v2"))
        except Exception:
            return CachedEmbeddingProvider(HashEmbeddingProvider())
    return CachedEmbeddingProvider(HashEmbeddingProvider())
