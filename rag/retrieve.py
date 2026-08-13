"""
Hybrid retrieval layer for Customer Support RAG.

Uses:
- Azure OpenAI -> embeddings
- Azure AI Search -> hybrid keyword/vector search
- Qdrant -> vector similarity search

Keeps the existing ProviderRegistry architecture so ingest.py
does not need any changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List
import logging
import os

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
# ABSTRACT EMBEDDING PROVIDER
# ============================================================

class AbstractEmbeddingProvider(ABC):
    """
    Abstract interface for embedding providers.
    """

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """
        Generate an embedding for a single piece of text.
        """
        pass

    @abstractmethod
    def embed_batch(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        """
        pass


# ============================================================
# ABSTRACT VECTOR STORE PROVIDER
# ============================================================

class AbstractVectorStoreProvider(ABC):
    """
    Abstract interface for vector store providers.
    """

    @abstractmethod
    def index_chunks(
        self,
        chunks: List[DocumentChunk],
    ) -> int:
        """
        Index document chunks.
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> List[SearchResult]:
        """
        Search for relevant document chunks.
        """
        pass

    @abstractmethod
    def get_document_stats(
        self,
    ) -> Dict[str, Any]:
        """
        Return document and chunk statistics.
        """
        pass

    @abstractmethod
    def clear(self):
        """
        Clear the vector store.
        """
        pass


# ============================================================
# AZURE OPENAI EMBEDDING PROVIDER
# ============================================================

class AzureOpenAIEmbeddingProvider(
    AbstractEmbeddingProvider
):
    """
    Generates embeddings using Azure OpenAI.
    """

    def __init__(self):
        logger.info(
            "Initializing Azure OpenAI embedding provider"
        )

        self.client = get_openai_client()

        self.model = os.getenv(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        )

        if not self.model:
            raise ValueError(
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT "
                "is not configured."
            )

    def embed_text(
        self,
        text: str,
    ) -> List[float]:
        """
        Generate an embedding for one text.
        """

        if not text or not text.strip():
            raise ValueError(
                "Cannot generate embedding for empty text."
            )

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
            )

            embedding = response.data[0].embedding

            logger.debug(
                "Generated embedding with dimension %d",
                len(embedding),
            )

            return embedding

        except Exception:
            logger.exception(
                "Failed to generate text embedding"
            )
            raise

    def embed_batch(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        """

        if not texts:
            return []

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )

            embeddings = [
                item.embedding
                for item in response.data
            ]

            logger.info(
                "Generated %d embeddings",
                len(embeddings),
            )

            return embeddings

        except Exception:
            logger.exception(
                "Failed to generate batch embeddings"
            )
            raise


# ============================================================
# AZURE + QDRANT VECTOR STORE
# ============================================================

class AzureQdrantVectorStoreProvider(
    AbstractVectorStoreProvider
):
    """
    Hybrid vector store provider.

    Documents are indexed into BOTH:

    1. Azure AI Search
    2. Qdrant

    Retrieval searches BOTH systems and combines
    their results.
    """

    def __init__(
        self,
        embedding_provider=None,
    ):
        logger.info(
            "Initializing Azure + Qdrant vector store"
        )

        self.embedding_provider = (
            embedding_provider
            or AzureOpenAIEmbeddingProvider()
        )

        # Azure AI Search
        self.search_client = get_search_client()

        # Qdrant
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")

        if not qdrant_url:
            raise ValueError(
                "QDRANT_URL is not configured."
            )

        self.qdrant = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
        )

        self.collection = os.getenv(
            "QDRANT_COLLECTION_NAME",
            "customer_support",
        )

        logger.info(
            "Hybrid vector store initialized. "
            "Qdrant collection: %s",
            self.collection,
        )

    # ========================================================
    # INDEX CHUNKS
    # ========================================================

    def index_chunks(
        self,
        chunks: List[DocumentChunk],
    ) -> int:
        """
        Generate embeddings and index chunks into
        both Azure AI Search and Qdrant.
        """

        if not chunks:
            logger.warning(
                "No chunks supplied for indexing."
            )
            return 0

        logger.info(
            "Indexing %d chunks",
            len(chunks),
        )

        # ----------------------------------------------------
        # Generate embeddings
        # ----------------------------------------------------

        texts = [
            chunk.text
            for chunk in chunks
        ]

        embeddings = (
            self.embedding_provider.embed_batch(
                texts
            )
        )

        if len(embeddings) != len(chunks):
            raise RuntimeError(
                "Number of generated embeddings does not "
                "match number of document chunks."
            )

        # ----------------------------------------------------
        # Azure AI Search documents
        # ----------------------------------------------------

        azure_documents = []

        for chunk, embedding in zip(
            chunks,
            embeddings,
        ):
            azure_documents.append(
                {
                    "id": chunk.chunk_id,
                    "content": chunk.text,
                    "document_name": (
                        chunk.document_name
                    ),
                    "page_number": (
                        chunk.page_number
                    ),
                    "vector": embedding,
                }
            )

        upload_documents(
            self.search_client,
            azure_documents,
        )

        logger.info(
            "Uploaded %d chunks to Azure AI Search",
            len(azure_documents),
        )

        # ----------------------------------------------------
        # Qdrant points
        # ----------------------------------------------------

        points = []

        for chunk, embedding in zip(
            chunks,
            embeddings,
        ):
            points.append(
                PointStruct(
                    id=chunk.chunk_id,
                    vector=embedding,
                    payload={
                        "content": chunk.text,
                        "document_name": (
                            chunk.document_name
                        ),
                        "page_number": (
                            chunk.page_number
                        ),
                        "chunk_id": chunk.chunk_id,
                        **chunk.metadata,
                    },
                )
            )

        self.qdrant.upsert(
            collection_name=self.collection,
            points=points,
        )

        logger.info(
            "Uploaded %d chunks to Qdrant",
            len(points),
        )

        logger.info(
            "Successfully indexed %d chunks "
            "into Azure AI Search and Qdrant",
            len(chunks),
        )

        return len(chunks)

    # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> List[SearchResult]:
        """
        Search Azure AI Search and Qdrant, then combine
        and deduplicate the results.
        """

        if not query or not query.strip():
            return []

        if top_k <= 0:
            return []

        logger.info(
            "Starting hybrid search for query: %s",
            query,
        )

        # ----------------------------------------------------
        # Create query embedding
        # ----------------------------------------------------

        embedding = (
            self.embedding_provider.embed_text(
                query
            )
        )

        results: List[SearchResult] = []

        # ====================================================
        # AZURE AI SEARCH
        # ====================================================

        try:
            azure_results = search_documents(
                self.search_client,
                query=query,
                query_vector=embedding,
                top=top_k,
            )

            logger.info(
                "Azure AI Search returned %d results",
                len(azure_results),
            )

            for document in azure_results:

                content = document.get(
                    "content",
                    "",
                )

                document_name = document.get(
                    "document_name",
                    "",
                )

                page_number = document.get(
                    "page_number",
                    1,
                )

                chunk_id = document.get(
                    "id",
                    "",
                )

                if not content or not chunk_id:
                    continue

                relevance = float(
                    document.get(
                        "@search.score",
                        0.0,
                    )
                    or 0.0
                )

                results.append(
                    SearchResult(
                        chunk_id=str(chunk_id),
                        text=content,
                        document_name=(
                            document_name
                        ),
                        page_number=int(
                            page_number
                        ),
                        relevance=relevance,
                        metadata={
                            "source": "azure_ai_search",
                        },
                    )
                )

        except Exception:
            logger.exception(
                "Azure AI Search retrieval failed"
            )

        # ====================================================
        # QDRANT
        # ====================================================

        try:
            qdrant_response = (
                self.qdrant.query_points(
                    collection_name=self.collection,
                    query=embedding,
                    limit=top_k,
                    with_payload=True,
                )
            )

            logger.info(
                "Qdrant returned %d results",
                len(qdrant_response.points),
            )

            for point in qdrant_response.points:

                payload = (
                    point.payload or {}
                )

                content = payload.get(
                    "content",
                    "",
                )

                if not content:
                    continue

                chunk_id = payload.get(
                    "chunk_id",
                    str(point.id),
                )

                document_name = payload.get(
                    "document_name",
                    "",
                )

                page_number = payload.get(
                    "page_number",
                    1,
                )

                results.append(
                    SearchResult(
                        chunk_id=str(chunk_id),
                        text=content,
                        document_name=(
                            document_name
                        ),
                        page_number=int(
                            page_number
                        ),
                        relevance=float(
                            point.score or 0.0
                        ),
                        metadata={
                            "source": "qdrant",
                        },
                    )
                )

        except Exception:
            logger.exception(
                "Qdrant retrieval failed"
            )

        # ====================================================
        # DEDUPLICATE RESULTS
        # ====================================================

        unique_results: Dict[
            str,
            SearchResult,
        ] = {}

        for result in results:

            existing = unique_results.get(
                result.chunk_id
            )

            if (
                existing is None
                or result.relevance
                > existing.relevance
            ):
                unique_results[
                    result.chunk_id
                ] = result

        final_results = list(
            unique_results.values()
        )

        # ----------------------------------------------------
        # Sort by relevance
        # ----------------------------------------------------

        final_results.sort(
            key=lambda result: (
                result.relevance
            ),
            reverse=True,
        )

        final_results = final_results[:top_k]

        logger.info(
            "Hybrid search completed. "
            "Returning %d results",
            len(final_results),
        )

        return final_results

    # ========================================================
    # DOCUMENT STATISTICS
    # ========================================================

    def get_document_stats(
        self,
    ) -> Dict[str, Any]:
        """
        Get document statistics from Azure AI Search.

        Azure AI Search is used as the source of truth for
        document/chunk statistics because the same chunks
        are indexed there.
        """

        try:
            total_chunks = (
                self.search_client.get_document_count()
            )

            documents = self.search_client.search(
                search_text="*",
                select=[
                    "document_name"
                ],
                top=1000,
            )

            document_names = sorted(
                {
                    document.get(
                        "document_name"
                    )
                    for document in documents
                    if document.get(
                        "document_name"
                    )
                }
            )

            return {
                "total_documents": len(
                    document_names
                ),
                "total_chunks": (
                    total_chunks or 0
                ),
                "documents": document_names,
            }

        except Exception:
            logger.exception(
                "Failed to retrieve document statistics"
            )
            raise

    # ========================================================
    # CLEAR
    # ========================================================

    def clear(self):
        """
        Clear operation is intentionally not implemented.

        Deleting Azure AI Search and Qdrant data should be
        performed explicitly to avoid accidental data loss.
        """

        logger.warning(
            "Clear operation is not implemented "
            "for the hybrid provider."
        )


# ============================================================
# PROVIDER REGISTRY
# ============================================================

class ProviderRegistry:
    """
    Central registry for embedding and vector store providers.

    Keeps a singleton-like provider instance so the rest of
    the application can use the same providers.
    """

    _embedding = None
    _vector = None

    @classmethod
    def get_embedding_provider(
        cls,
    ) -> AbstractEmbeddingProvider:
        """
        Return the configured embedding provider.
        """

        if cls._embedding is None:

            cls._embedding = (
                AzureOpenAIEmbeddingProvider()
            )

        return cls._embedding

    @classmethod
    def get_vector_store_provider(
        cls,
    ) -> AbstractVectorStoreProvider:
        """
        Return the configured hybrid vector store provider.
        """

        if cls._vector is None:

            cls._vector = (
                AzureQdrantVectorStoreProvider(
                    cls.get_embedding_provider()
                )
            )

        return cls._vector

# ============================================================
# CONVENIENCE RETRIEVAL FUNCTION
# ============================================================

def retrieve_documents(
    query: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Compatibility function used by RAGPipeline.
    """

    if not query or not query.strip():
        return []

    provider = ProviderRegistry.get_vector_store_provider()

    results = provider.search(
        query=query.strip(),
        top_k=top_k,
    )

    return [
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