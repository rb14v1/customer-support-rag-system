"""
Hybrid retrieval layer for Customer Support RAG.

Uses:
- Azure OpenAI -> embeddings
- Azure AI Search -> hybrid keyword/vector search
- Qdrant -> vector similarity search
- Result Fusion -> normalized fusion & relevance gating

Includes Mock providers and ProviderRegistry for testing and dependency injection.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set


from django.conf import settings
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from azure_services.azure_config import (
    get_openai_client,
    get_search_client,
)
from azure_services.search_service import (
    upload_documents,
    search_documents,
)

load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================
# DOCUMENT MODELS
# ============================================================

@dataclass
class DocumentChunk:
    """
    Represents one chunk of an ingested document.
    """
    chunk_id: str
    text: str
    document_name: str
    page_number: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """
    Represents one retrieved search result.
    """
    chunk_id: str
    text: str
    document_name: str
    page_number: int
    relevance: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# ABSTRACT INTERFACES
# ============================================================

class AbstractEmbeddingProvider(ABC):
    """
    Abstract interface for embedding providers.
    """
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass


class AbstractVectorStoreProvider(ABC):
    """
    Abstract interface for vector store providers.
    """
    @abstractmethod
    def index_chunks(self, chunks: List[DocumentChunk]) -> int:
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 3, min_score: Optional[float] = None) -> List[SearchResult]:
        pass

    @abstractmethod
    def get_document_stats(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def clear(self):
        pass


class AbstractLLMProvider(ABC):
    """
    Abstract interface for LLM generation providers.
    """
    @abstractmethod
    def generate(self, prompt: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        pass


# ============================================================
# MOCK PROVIDERS FOR TESTING
# ============================================================

class MockEmbeddingProvider(AbstractEmbeddingProvider):
    """
    Deterministic mock embedding provider for tests.
    """
    def __init__(self, dim: int = 64):
        logger.info("Starting MockEmbeddingProvider initialization (dim=%d)", dim)
        self.dim = dim
        logger.info("Finished MockEmbeddingProvider initialization")

    def embed_text(self, text: str) -> List[float]:
        logger.debug("Starting MockEmbeddingProvider.embed_text")
        try:
            if not text or not text.strip():
                raise ValueError("Cannot generate embedding for empty text.")
            h = hashlib.sha256(text.encode('utf-8')).hexdigest()
            nums = [int(h[i:i+2], 16) / 255.0 for i in range(0, min(len(h), self.dim * 2), 2)]
            while len(nums) < self.dim:
                nums.extend(nums)
            res = nums[:self.dim]
            logger.debug("Finished MockEmbeddingProvider.embed_text")
            return res
        except Exception:
            logger.exception("Failed in MockEmbeddingProvider.embed_text")
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        logger.debug("Starting MockEmbeddingProvider.embed_batch")
        try:
            res = [self.embed_text(t) for t in texts]
            logger.debug("Finished MockEmbeddingProvider.embed_batch")
            return res
        except Exception:
            logger.exception("Failed in MockEmbeddingProvider.embed_batch")
            raise


class MockVectorStoreProvider(AbstractVectorStoreProvider):
    """
    In-memory mock vector store provider for fast unit testing.
    """
    def __init__(self, embedding_provider: Optional[AbstractEmbeddingProvider] = None):
        logger.info("Starting MockVectorStoreProvider initialization")
        try:
            self.embedding_provider = embedding_provider or MockEmbeddingProvider()
            self.chunks: Dict[str, DocumentChunk] = {}
            logger.info("Finished MockVectorStoreProvider initialization")
        except Exception:
            logger.exception("Failed to initialize MockVectorStoreProvider")
            raise

    def index_chunks(self, chunks: List[DocumentChunk]) -> int:
        logger.info("Starting MockVectorStoreProvider.index_chunks (%d chunks)", len(chunks))
        try:
            for chunk in chunks:
                self.chunks[chunk.chunk_id] = chunk
            logger.info("Finished MockVectorStoreProvider.index_chunks (%d indexed)", len(chunks))
            return len(chunks)
        except Exception:
            logger.exception("Failed in MockVectorStoreProvider.index_chunks")
            raise

    def search(self, query: str, top_k: int = 3, min_score: Optional[float] = None) -> List[SearchResult]:
        logger.info("Starting MockVectorStoreProvider.search for query: '%s'", query)
        try:
            if not query or not query.strip() or not self.chunks or top_k <= 0:
                logger.info("Finished MockVectorStoreProvider.search (empty/invalid input)")
                return []

            # Determine threshold
            if min_score is not None:
                min_threshold = float(min_score)
            else:
                min_threshold = float(
                    getattr(settings, "RAG_MIN_QDRANT_SCORE", os.getenv("RAG_MIN_QDRANT_SCORE", "0.50"))
                )
                if hasattr(settings, "RAG_MIN_RELEVANCE_SCORE"):
                    setting_thresh = getattr(settings, "RAG_MIN_RELEVANCE_SCORE")
                    if setting_thresh is not None and float(setting_thresh) > 0.9:
                        min_threshold = float(setting_thresh)

            stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "for", "to", "of", "and", "or", "your", "our", "you", "we", "can", "be", "with", "this", "that", "it", "what", "how", "why", "when", "where", "do", "does", "did"}
            query_words = set(re.findall(r"\w+", query.lower())) - stop_words
            results: List[SearchResult] = []

            for chunk in self.chunks.values():
                text_words = set(re.findall(r"\w+", chunk.text.lower())) - stop_words
                overlap = len(query_words.intersection(text_words))
                if overlap > 0:
                    score = min(0.99, 0.60 + (overlap * 0.15))
                else:
                    score = 0.10

                results.append(
                    SearchResult(
                        chunk_id=chunk.chunk_id,
                        text=chunk.text,
                        document_name=chunk.document_name,
                        page_number=chunk.page_number,
                        relevance=round(score, 4),
                        metadata=chunk.metadata,
                    )
                )

            results.sort(key=lambda r: r.relevance, reverse=True)
            if min_threshold >= 0.9:
                results = [r for r in results if r.relevance >= min_threshold]

            res = results[:top_k]
            logger.info("Finished MockVectorStoreProvider.search (%d results returned)", len(res))
            return res
        except Exception:
            logger.exception("Failed in MockVectorStoreProvider.search")
            return []

    def get_document_stats(self) -> Dict[str, Any]:
        logger.info("Starting MockVectorStoreProvider.get_document_stats")
        try:
            docs = sorted({c.document_name for c in self.chunks.values()})
            stats = {
                "total_documents": len(docs),
                "total_chunks": len(self.chunks),
                "documents": docs,
            }
            logger.info("Finished MockVectorStoreProvider.get_document_stats")
            return stats
        except Exception:
            logger.exception("Failed in MockVectorStoreProvider.get_document_stats")
            return {"total_documents": 0, "total_chunks": 0, "documents": []}

    def clear(self):
        logger.info("Starting MockVectorStoreProvider.clear")
        try:
            self.chunks.clear()
            logger.info("Finished MockVectorStoreProvider.clear")
        except Exception:
            logger.exception("Failed in MockVectorStoreProvider.clear")







    def get_document_stats(self) -> Dict[str, Any]:
        docs = sorted({c.document_name for c in self.chunks.values()})
        return {
            "total_documents": len(docs),
            "total_chunks": len(self.chunks),
            "documents": docs,
        }

    def clear(self):
        self.chunks.clear()


# ============================================================
# AZURE OPENAI EMBEDDING PROVIDER
# ============================================================

class AzureOpenAIEmbeddingProvider(AbstractEmbeddingProvider):
    """
    Generates embeddings using Azure OpenAI.
    """
    def __init__(self):
        logger.info("Starting AzureOpenAIEmbeddingProvider initialization")
        self.client = get_openai_client()
        self.model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        if not self.model:
            raise ValueError("AZURE_OPENAI_EMBEDDING_DEPLOYMENT is not configured.")
        logger.info("Finished AzureOpenAIEmbeddingProvider initialization")

    def embed_text(self, text: str) -> List[float]:
        logger.debug("Starting AzureOpenAIEmbeddingProvider.embed_text")
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text.")
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            embedding = response.data[0].embedding
            logger.debug("Finished AzureOpenAIEmbeddingProvider.embed_text (dimension %d)", len(embedding))
            return embedding
        except Exception:
            logger.exception("Failed to generate text embedding")
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        logger.info("Starting AzureOpenAIEmbeddingProvider.embed_batch for %d texts", len(texts) if texts else 0)
        if not texts:
            logger.info("Finished AzureOpenAIEmbeddingProvider.embed_batch (empty input)")
            return []
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            embeddings = [item.embedding for item in response.data]
            logger.info("Finished AzureOpenAIEmbeddingProvider.embed_batch (generated %d embeddings)", len(embeddings))
            return embeddings
        except Exception:
            logger.exception("Failed to generate batch embeddings")
            raise


# ============================================================
# AZURE + QDRANT HYBRID VECTOR STORE PROVIDER
# ============================================================

class AzureQdrantVectorStoreProvider(AbstractVectorStoreProvider):
    """
    Hybrid vector store provider.

    Documents are indexed into BOTH:
    1. Azure AI Search
    2. Qdrant

    Retrieval searches BOTH systems and performs result fusion.
    """
    def __init__(self, embedding_provider: Optional[AbstractEmbeddingProvider] = None):
        logger.info("Starting AzureQdrantVectorStoreProvider initialization")
        self.embedding_provider = embedding_provider or AzureOpenAIEmbeddingProvider()

        # Azure AI Search client
        self.search_client = get_search_client()

        # Qdrant client
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        if not qdrant_url:
            raise ValueError("QDRANT_URL is not configured.")

        self.qdrant = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
        )

        self.collection = os.getenv("QDRANT_COLLECTION_NAME", "customer_support")
        logger.info("Finished AzureQdrantVectorStoreProvider initialization. Collection: %s", self.collection)

    def index_chunks(self, chunks: List[DocumentChunk]) -> int:
        logger.info("Starting AzureQdrantVectorStoreProvider.index_chunks for %d chunks", len(chunks) if chunks else 0)
        if not chunks:
            logger.warning("No chunks supplied for indexing.")
            logger.info("Finished AzureQdrantVectorStoreProvider.index_chunks (0 indexed)")
            return 0

        try:
            texts = [chunk.text for chunk in chunks]
            embeddings = self.embedding_provider.embed_batch(texts)

            if len(embeddings) != len(chunks):
                raise RuntimeError("Generated embeddings count does not match chunks count.")

            # Index to Azure AI Search
            azure_documents = []
            for chunk, embedding in zip(chunks, embeddings):
                azure_documents.append({
                    "id": chunk.chunk_id,
                    "content": chunk.text,
                    "document_name": chunk.document_name,
                    "page_number": chunk.page_number,
                    "vector": embedding,
                })
            upload_documents(self.search_client, azure_documents)
            logger.info("Uploaded %d chunks to Azure AI Search", len(azure_documents))

            # Index to Qdrant
            import uuid
            points = []
            for chunk, embedding in zip(chunks, embeddings):
                point_id = chunk.chunk_id
                try:
                    valid_qdrant_id = str(uuid.UUID(str(point_id)))
                except ValueError:
                    valid_qdrant_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(point_id)))

                points.append(
                    PointStruct(
                        id=valid_qdrant_id,
                        vector=embedding,
                        payload={
                            "content": chunk.text,
                            "document_name": chunk.document_name,
                            "page_number": chunk.page_number,
                            "chunk_id": chunk.chunk_id,
                            **chunk.metadata,
                        },
                    )
                )
            self.qdrant.upsert(
                collection_name=self.collection,
                points=points,
            )
            logger.info("Uploaded %d chunks to Qdrant", len(points))
            logger.info("Finished AzureQdrantVectorStoreProvider.index_chunks")
            return len(chunks)
        except Exception:
            logger.exception("Failed in AzureQdrantVectorStoreProvider.index_chunks")
            raise


    def search(self, query: str, top_k: int = 3, min_score: Optional[float] = None) -> List[SearchResult]:
        logger.info("Starting AzureQdrantVectorStoreProvider.search for query: '%s'", query)
        if not query or not query.strip() or top_k <= 0:
            logger.info("Finished AzureQdrantVectorStoreProvider.search (empty/invalid query)")
            return []

        try:
            # Read threshold from parameter, .env, or Django settings
            if min_score is not None:
                min_threshold = float(min_score)
            else:
                min_threshold = float(
                    getattr(settings, "RAG_MIN_QDRANT_SCORE", os.getenv("RAG_MIN_QDRANT_SCORE", "0.55"))
                )
                if hasattr(settings, "RAG_MIN_RELEVANCE_SCORE"):
                    setting_thresh = getattr(settings, "RAG_MIN_RELEVANCE_SCORE")
                    if setting_thresh is not None and float(setting_thresh) > 0.9:
                        min_threshold = float(setting_thresh)

            logger.info("Executing hybrid search for query: '%s' (top_k=%d, threshold=%.2f)", query, top_k, min_threshold)

            embedding = self.embedding_provider.embed_text(query)

            qdrant_candidates: Dict[str, SearchResult] = {}
            azure_candidates: Dict[str, SearchResult] = {}

            # 1. Qdrant Search
            try:
                qdrant_resp = self.qdrant.query_points(
                    collection_name=self.collection,
                    query=embedding,
                    limit=top_k * 2,
                    with_payload=True,
                )
                for point in qdrant_resp.points:
                    payload = point.payload or {}
                    content = payload.get("content", "")
                    if not content:
                        continue
                    cid = str(payload.get("chunk_id", str(point.id)))
                    doc_name = str(payload.get("document_name", ""))
                    page_num = int(payload.get("page_number", 1))
                    score = float(point.score or 0.0)
                    qdrant_candidates[cid] = SearchResult(
                        chunk_id=cid,
                        text=content,
                        document_name=doc_name,
                        page_number=page_num,
                        relevance=score,
                        metadata={"source": "qdrant", "raw_score": score},
                    )
                logger.info("Qdrant returned %d candidates. Top raw score: %.4f",
                            len(qdrant_candidates),
                            max([c.relevance for c in qdrant_candidates.values()], default=0.0))
            except Exception:
                logger.exception("Qdrant retrieval failed")

            # 2. Azure AI Search
            try:
                azure_resp = search_documents(
                    self.search_client,
                    query=query,
                    query_vector=embedding,
                    top=top_k * 2,
                )
                for doc in azure_resp:
                    content = doc.get("content", "")
                    cid = str(doc.get("id", ""))
                    if not content or not cid:
                        continue
                    doc_name = str(doc.get("document_name", ""))
                    page_num = int(doc.get("page_number", 1))
                    score = float(doc.get("@search.score", 0.0) or 0.0)
                    azure_candidates[cid] = SearchResult(
                        chunk_id=cid,
                        text=content,
                        document_name=doc_name,
                        page_number=page_num,
                        relevance=score,
                        metadata={"source": "azure_ai_search", "raw_score": score},
                    )
                logger.info("Azure AI Search returned %d candidates", len(azure_candidates))
            except Exception:
                logger.exception("Azure AI Search retrieval failed")

            # 3. Result Fusion & Deduplication
            all_chunk_ids = set(qdrant_candidates.keys()).union(set(azure_candidates.keys()))
            fused_results: List[SearchResult] = []

            max_azure_score = max([c.relevance for c in azure_candidates.values()], default=1.0) or 1.0

            for cid in all_chunk_ids:
                q_res = qdrant_candidates.get(cid)
                a_res = azure_candidates.get(cid)
                rep = q_res or a_res
                if not rep:
                    continue

                q_score = q_res.relevance if q_res else 0.0
                a_score = a_res.relevance if a_res else 0.0

                # Normalize scores
                norm_q = min(1.0, max(0.0, q_score))
                norm_a = min(1.0, max(0.0, a_score / max_azure_score)) if max_azure_score > 0 else 0.0

                # Dual-system fusion score preserving raw vector similarity
                if q_res and a_res:
                    fused_score = max(q_score, 0.50 * norm_q + 0.40 * norm_a + 0.10)
                elif q_res:
                    fused_score = q_score
                else:
                    fused_score = 0.80 * norm_a

                # Document topic alignment boost when document name keywords match query
                doc_keywords = set(rep.document_name.lower().replace("_", " ").replace(".pdf", "").split())
                query_words = set(query.lower().split())
                if doc_keywords.intersection(query_words):
                    fused_score = min(1.0, fused_score + 0.10)

                fused_score = round(min(1.0, fused_score), 4)

                # Relevance Gate
                if fused_score >= min_threshold:
                    fused_results.append(
                        SearchResult(
                            chunk_id=rep.chunk_id,
                            text=rep.text,
                            document_name=rep.document_name,
                            page_number=rep.page_number,
                            relevance=fused_score,
                            metadata={
                                "qdrant_score": q_score,
                                "azure_score": a_score,
                                "fused_score": fused_score,
                                "dual_supported": bool(q_res and a_res),
                            },
                        )
                    )
                else:
                    logger.info("Rejected candidate chunk '%s' (%s p.%d): fused score %.4f < threshold %.2f",
                                cid, rep.document_name, rep.page_number, fused_score, min_threshold)

            fused_results.sort(key=lambda r: r.relevance, reverse=True)

            # Diversified selection to avoid a single document dominating all top_k slots
            diversified_results: List[SearchResult] = []
            doc_counts: Dict[str, int] = {}
            for res in fused_results:
                d_name = res.document_name
                if doc_counts.get(d_name, 0) < 2:
                    diversified_results.append(res)
                    doc_counts[d_name] = doc_counts.get(d_name, 0) + 1
                if len(diversified_results) >= top_k:
                    break

            # Fallback if diversified list has fewer than top_k items
            if len(diversified_results) < top_k and len(fused_results) > len(diversified_results):
                for res in fused_results:
                    if res not in diversified_results:
                        diversified_results.append(res)
                    if len(diversified_results) >= top_k:
                        break

            final_results = diversified_results

            logger.info("Hybrid search completed. %d candidates passed gate, returning top %d",
                        len(fused_results), len(final_results))
            logger.info("Finished AzureQdrantVectorStoreProvider.search")
            return final_results
        except Exception:
            logger.exception("Failed in AzureQdrantVectorStoreProvider.search")
            return []


    def get_document_stats(self) -> Dict[str, Any]:
        logger.info("Starting AzureQdrantVectorStoreProvider.get_document_stats")
        try:
            total_chunks = self.search_client.get_document_count()
            documents = self.search_client.search(
                search_text="*",
                select=["document_name"],
                top=1000,
            )
            document_names = sorted(
                {doc.get("document_name") for doc in documents if doc.get("document_name")}
            )
            stats = {
                "total_documents": len(document_names),
                "total_chunks": total_chunks or 0,
                "documents": document_names,
            }
            logger.info("Finished AzureQdrantVectorStoreProvider.get_document_stats")
            return stats
        except Exception:
            logger.exception("Failed to retrieve document statistics")
            raise

    def clear(self):
        logger.info("Starting AzureQdrantVectorStoreProvider.clear")
        logger.warning("Clear operation is not implemented for hybrid provider.")
        logger.info("Finished AzureQdrantVectorStoreProvider.clear")


# ============================================================
# DEPENDENCY INJECTION PROVIDER REGISTRY
# ============================================================

class ProviderRegistry:
    """
    Central registry for embedding, vector store, and LLM providers.
    Supports dependency injection and fallback detection.
    """
    _embedding_provider: Optional[AbstractEmbeddingProvider] = None
    _vector_store_provider: Optional[AbstractVectorStoreProvider] = None
    _llm_provider: Optional[AbstractLLMProvider] = None

    @classmethod
    def get_embedding_provider(cls) -> AbstractEmbeddingProvider:
        logger.debug("Starting ProviderRegistry.get_embedding_provider")
        if cls._embedding_provider is None:
            if os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_API_KEY"):
                try:
                    cls._embedding_provider = AzureOpenAIEmbeddingProvider()
                except Exception as e:
                    logger.warning("Falling back to MockEmbeddingProvider: %s", str(e))
                    cls._embedding_provider = MockEmbeddingProvider()
            else:
                cls._embedding_provider = MockEmbeddingProvider()
        logger.debug("Finished ProviderRegistry.get_embedding_provider")
        return cls._embedding_provider

    @classmethod
    def set_embedding_provider(cls, provider: AbstractEmbeddingProvider) -> None:
        logger.info("Starting ProviderRegistry.set_embedding_provider")
        if not isinstance(provider, AbstractEmbeddingProvider):
            raise TypeError("Provider must implement AbstractEmbeddingProvider interface.")
        cls._embedding_provider = provider
        logger.info("Finished ProviderRegistry.set_embedding_provider")

    @classmethod
    def get_vector_store_provider(cls) -> AbstractVectorStoreProvider:
        logger.debug("Starting ProviderRegistry.get_vector_store_provider")
        if cls._vector_store_provider is None:
            if (
                os.getenv("QDRANT_URL")
                and os.getenv("AZURE_SEARCH_ENDPOINT")
                and os.getenv("AZURE_SEARCH_API_KEY")
            ):
                try:
                    cls._vector_store_provider = AzureQdrantVectorStoreProvider(
                        cls.get_embedding_provider()
                    )
                except Exception as e:
                    logger.warning("Falling back to MockVectorStoreProvider: %s", str(e))
                    cls._vector_store_provider = MockVectorStoreProvider(
                        cls.get_embedding_provider()
                    )
            else:
                cls._vector_store_provider = MockVectorStoreProvider(
                    cls.get_embedding_provider()
                )
        logger.debug("Finished ProviderRegistry.get_vector_store_provider")
        return cls._vector_store_provider

    @classmethod
    def set_vector_store_provider(cls, provider: AbstractVectorStoreProvider) -> None:
        logger.info("Starting ProviderRegistry.set_vector_store_provider")
        if not isinstance(provider, AbstractVectorStoreProvider):
            raise TypeError("Provider must implement AbstractVectorStoreProvider interface.")
        cls._vector_store_provider = provider
        logger.info("Finished ProviderRegistry.set_vector_store_provider")

    @classmethod
    def get_llm_provider(cls) -> AbstractLLMProvider:
        logger.debug("Starting ProviderRegistry.get_llm_provider")
        if cls._llm_provider is None:
            from rag.rag import AzureOpenAILLMProvider, MockLLMProvider
            if os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_API_KEY"):
                try:
                    cls._llm_provider = AzureOpenAILLMProvider()
                except Exception as e:
                    logger.warning("Falling back to MockLLMProvider: %s", str(e))
                    cls._llm_provider = MockLLMProvider()
            else:
                cls._llm_provider = MockLLMProvider()
        logger.debug("Finished ProviderRegistry.get_llm_provider")
        return cls._llm_provider

    @classmethod
    def set_llm_provider(cls, provider: AbstractLLMProvider) -> None:
        logger.info("Starting ProviderRegistry.set_llm_provider")
        if not isinstance(provider, AbstractLLMProvider):
            raise TypeError("Provider must implement AbstractLLMProvider interface.")
        cls._llm_provider = provider
        logger.info("Finished ProviderRegistry.set_llm_provider")

    @classmethod
    def reset_defaults(cls) -> None:
        logger.info("Starting ProviderRegistry.reset_defaults")
        cls._embedding_provider = None
        cls._vector_store_provider = None
        cls._llm_provider = None
        logger.info("Finished ProviderRegistry.reset_defaults")


# ============================================================
# CONVENIENCE RETRIEVAL FUNCTION
# ============================================================

def retrieve_documents(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Convenience function returning dictionary representation of retrieved chunks.
    """
    logger.info("Starting retrieve_documents for query: '%s'", query)
    if not query or not query.strip():
        logger.info("Finished retrieve_documents (empty query)")
        return []

    try:
        provider = ProviderRegistry.get_vector_store_provider()
        results = provider.search(query=query.strip(), top_k=top_k)

        res = [
            {
                "chunk_id": result.chunk_id,
                "content": result.text,
                "text": result.text,
                "document": result.document_name,
                "document_name": result.document_name,
                "page": result.page_number,
                "page_number": result.page_number,
                "relevance": result.relevance,
                "score": result.relevance,
                "metadata": result.metadata,
            }
            for result in results
        ]
        logger.info("Finished retrieve_documents (%d documents retrieved)", len(res))
        return res
    except Exception:
        logger.exception("Failed in retrieve_documents convenience function")
        raise