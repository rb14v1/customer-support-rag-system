"""
Retrieval module defining abstract interfaces for Embedding and VectorStore providers,
along with default mock implementations for local testing and a ProviderRegistry for DI.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging
import math
import re
from typing import Any, Dict, List, Optional
import zlib
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    document_name: str
    page_number: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    chunk_id: str
    text: str
    document_name: str
    page_number: int
    relevance: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class AbstractEmbeddingProvider(ABC):
    """
    Interface for text embedding generation.
    Feature/azure branch can inject AzureOpenAIEmbeddingProvider.
    """

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding vector for a single string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a list of strings."""
        pass


class AbstractVectorStoreProvider(ABC):
    """
    Interface for vector store indexing and similarity search.
    Feature/azure branch can inject AzureAISearchVectorStoreProvider.
    """

    @abstractmethod
    def index_chunks(self, chunks: List[DocumentChunk]) -> int:
        """
        Upload/index document chunks into the vector store.
        Returns the count of successfully indexed chunks.
        """
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 3) -> List[SearchResult]:
        """
        Perform similarity search for a given query string.
        Returns top-k matching SearchResult items.
        """
        pass

    @abstractmethod
    def get_document_stats(self) -> Dict[str, Any]:
        """
        Return document index statistics: total documents, total chunks, document names list.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear indexed chunks (used for testing or re-ingestion)."""
        pass


class AbstractLLMProvider(ABC):
    """
    Interface for LLM response generation.
    Feature/azure branch can inject AzureOpenAILLMProvider.
    """

    @abstractmethod
    def generate_response(self, prompt: str, search_results: List[SearchResult]) -> str:
        """Generate text response from prompt and search results."""
        pass


STOP_WORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he', 'in', 'is', 'it', 'its',
    'of', 'on', 'that', 'the', 'to', 'was', 'were', 'will', 'with', 'what', 'how', 'do', 'does', 'i', 'my',
    'you', 'your', 'can', 'should', 'would', 'could', 'about', 'this', 'there', 'their', 'or', 'if', 'any'
}


def _tokenize_text(text: str) -> List[str]:
    if not text or not isinstance(text, str):
        return []
    words = re.findall(r'\b[a-z0-9]+\b', text.lower())
    tokens = []
    for w in words:
        if w in STOP_WORDS:
            continue
        if len(w) > 4 and w.endswith('ing'):
            w = w[:-3]
        elif len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
            w = w[:-1]
        tokens.append(w)
    return tokens


class MockEmbeddingProvider(AbstractEmbeddingProvider):
    """
    Default lightweight local mock embedding provider for local dev and testing.
    Uses stopword-filtered normalized token feature hashing to generate float vectors.
    """

    def __init__(self, dim: int = 512):
        if dim <= 0:
            raise ValueError("Embedding dimension must be a positive integer.")
        self.dim = dim

    def _hash_vector(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = _tokenize_text(text)
        if not tokens:
            return vec
        for token in tokens:
            idx = zlib.crc32(token.encode('utf-8')) % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_text(self, text: str) -> List[float]:
        try:
            return self._hash_vector(text)
        except Exception as e:
            logger.error("Error generating text embedding: %s", str(e))
            return [0.0] * self.dim

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not isinstance(texts, list):
            raise TypeError("texts must be a list of strings.")
        return [self.embed_text(t) for t in texts]


class MockVectorStoreProvider(AbstractVectorStoreProvider):
    """
    Default in-memory mock vector store provider for local dev and testing.
    Stores chunks in memory and computes cosine similarity search.
    Includes document title metadata weighting for accurate local ranking.
    """

    def __init__(self, embedding_provider: Optional[AbstractEmbeddingProvider] = None):
        self.embedding_provider = embedding_provider or MockEmbeddingProvider()
        self.chunks: List[DocumentChunk] = []
        self.embeddings: List[List[float]] = []

    def _prepare_chunk_text(self, chunk: DocumentChunk) -> str:
        doc_title_clean = chunk.document_name.replace('.pdf', '').replace('_', ' ')
        return f"{doc_title_clean} {doc_title_clean} {doc_title_clean} {chunk.text}"

    def index_chunks(self, chunks: List[DocumentChunk]) -> int:
        if not chunks:
            return 0

        logger.info("Indexing %d document chunks in MockVectorStoreProvider", len(chunks))
        try:
            existing_map = {chunk.chunk_id: idx for idx, chunk in enumerate(self.chunks)}
            new_chunks_to_embed = []

            for chunk in chunks:
                combined_text = self._prepare_chunk_text(chunk)
                if chunk.chunk_id in existing_map:
                    idx = existing_map[chunk.chunk_id]
                    self.chunks[idx] = chunk
                    self.embeddings[idx] = self.embedding_provider.embed_text(combined_text)
                else:
                    new_chunks_to_embed.append((chunk, combined_text))

            if new_chunks_to_embed:
                texts = [item[1] for item in new_chunks_to_embed]
                chunks_to_add = [item[0] for item in new_chunks_to_embed]
                new_embeddings = self.embedding_provider.embed_batch(texts)
                self.chunks.extend(chunks_to_add)
                self.embeddings.extend(new_embeddings)

            logger.info("MockVectorStoreProvider now holds %d total chunks", len(self.chunks))
            return len(chunks)
        except Exception as e:
            logger.exception("Error indexing chunks in MockVectorStoreProvider: %s", str(e))
            raise RuntimeError(f"Error indexing chunks: {str(e)}") from e

    def search(self, query: str, top_k: int = 3) -> List[SearchResult]:
        if not self.chunks or not query or not query.strip():
            logger.info("Vector search skipped (empty query or empty store)")
            return []

        logger.info("Executing vector similarity search for query: '%s' (top_k=%d)", query.strip(), top_k)
        try:
            query_vec = np.array(self.embedding_provider.embed_text(query), dtype=float)
            query_norm = np.linalg.norm(query_vec)

            if query_norm == 0:
                logger.warning("Query vector norm is 0 for query: '%s'", query)
                return []

            results: List[SearchResult] = []
            for chunk, emb in zip(self.chunks, self.embeddings):
                emb_vec = np.array(emb, dtype=float)
                emb_norm = np.linalg.norm(emb_vec)
                if emb_norm == 0:
                    score = 0.0
                else:
                    score = float(np.dot(query_vec, emb_vec) / (query_norm * emb_norm))

                results.append(
                    SearchResult(
                        chunk_id=chunk.chunk_id,
                        text=chunk.text,
                        document_name=chunk.document_name,
                        page_number=chunk.page_number,
                        relevance=score,
                        metadata=chunk.metadata,
                    )
                )

            # Sort by relevance descending
            results.sort(key=lambda x: x.relevance, reverse=True)
            top_results = results[:top_k]
            if top_results:
                logger.info("Search returned %d top results. Highest score: %.4f", len(top_results), top_results[0].relevance)
            return top_results
        except Exception as e:
            logger.exception("Error executing vector search for query '%s': %s", query, str(e))
            raise RuntimeError(f"Vector search failed: {str(e)}") from e

    def get_document_stats(self) -> Dict[str, Any]:
        docs = sorted(list({c.document_name for c in self.chunks}))
        return {
            "total_documents": len(docs),
            "total_chunks": len(self.chunks),
            "documents": docs,
        }

    def clear(self) -> None:
        logger.info("Clearing MockVectorStoreProvider index")
        self.chunks.clear()
        self.embeddings.clear()


class ProviderRegistry:
    """
    Central Dependency Injection Registry for RAG providers.
    Enables Person 2 to inject Azure providers cleanly without changing RAG core.
    """

    _embedding_provider: Optional[AbstractEmbeddingProvider] = None
    _vector_store_provider: Optional[AbstractVectorStoreProvider] = None
    _llm_provider: Optional[AbstractLLMProvider] = None

    @classmethod
    def get_embedding_provider(cls) -> AbstractEmbeddingProvider:
        if cls._embedding_provider is None:
            cls._embedding_provider = MockEmbeddingProvider()
        return cls._embedding_provider

    @classmethod
    def set_embedding_provider(cls, provider: AbstractEmbeddingProvider) -> None:
        if not isinstance(provider, AbstractEmbeddingProvider):
            raise TypeError("Provider must implement AbstractEmbeddingProvider interface.")
        logger.info("Registering custom EmbeddingProvider: %s", provider.__class__.__name__)
        cls._embedding_provider = provider

    @classmethod
    def get_vector_store_provider(cls) -> AbstractVectorStoreProvider:
        if cls._vector_store_provider is None:
            cls._vector_store_provider = MockVectorStoreProvider(cls.get_embedding_provider())
        return cls._vector_store_provider

    @classmethod
    def set_vector_store_provider(cls, provider: AbstractVectorStoreProvider) -> None:
        if not isinstance(provider, AbstractVectorStoreProvider):
            raise TypeError("Provider must implement AbstractVectorStoreProvider interface.")
        logger.info("Registering custom VectorStoreProvider: %s", provider.__class__.__name__)
        cls._vector_store_provider = provider

    @classmethod
    def get_llm_provider(cls) -> AbstractLLMProvider:
        from rag.rag import MockLLMProvider
        if cls._llm_provider is None:
            cls._llm_provider = MockLLMProvider()
        return cls._llm_provider

    @classmethod
    def set_llm_provider(cls, provider: AbstractLLMProvider) -> None:
        if not isinstance(provider, AbstractLLMProvider):
            raise TypeError("Provider must implement AbstractLLMProvider interface.")
        logger.info("Registering custom LLMProvider: %s", provider.__class__.__name__)
        cls._llm_provider = provider

    @classmethod
    def reset_defaults(cls) -> None:
        logger.info("Resetting ProviderRegistry to default mock providers")
        cls._embedding_provider = None
        cls._vector_store_provider = None
        cls._llm_provider = None
