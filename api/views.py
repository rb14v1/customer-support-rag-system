"""
Django REST Framework Views for Customer Support RAG System.
"""

import logging
from pathlib import Path
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from rag.ingest import IngestionPipeline
from rag.rag import RAGPipeline
from rag.retrieve import ProviderRegistry
from api.serializers import (
    ChatQuerySerializer,
    ChatResponseSerializer,
    DocumentStatsSerializer,
    HealthCheckSerializer,
    IngestRequestSerializer,
    IngestResponseSerializer,
)

logger = logging.getLogger(__name__)


def _ensure_auto_ingested():
    """Helper to auto-ingest PDFs from DATA_DIR if store is currently empty."""
    try:
        vector_store = ProviderRegistry.get_vector_store_provider()
        stats = vector_store.get_document_stats()
        if stats.get("total_chunks", 0) == 0:
            data_dir = getattr(settings, "DATA_DIR", Path(settings.BASE_DIR) / "data")
            if Path(data_dir).is_dir():
                logger.info("Auto-ingesting sample PDF documents from %s", data_dir)
                pipeline = IngestionPipeline()
                pipeline.ingest_directory(data_dir)
    except Exception as e:
        logger.exception("Error during auto-ingestion: %s", str(e))


class HealthCheckView(APIView):
    """GET /api/health/ - Returns health status and index stats."""

    def get(self, request):
        logger.info("GET /api/health/ requested")
        try:
            _ensure_auto_ingested()
            vector_store = ProviderRegistry.get_vector_store_provider()
            stats = vector_store.get_document_stats()

            data = {
                "status": "healthy",
                "documents_indexed": stats.get("total_documents", 0),
                "chunks_indexed": stats.get("total_chunks", 0),
                "vector_store_provider": vector_store.__class__.__name__,
            }
            serializer = HealthCheckSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("HealthCheckView failure: %s", str(e))
            return Response(
                {"error": "Unable to check system health."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DocumentIngestView(APIView):
    """POST /api/ingest/ - Triggers document ingestion from data/ directory."""

    def post(self, request):
        logger.info("POST /api/ingest/ requested")
        try:
            serializer = IngestRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            custom_dir = serializer.validated_data.get("data_dir")
            target_dir = Path(custom_dir) if custom_dir else getattr(settings, "DATA_DIR", Path(settings.BASE_DIR) / "data")

            if not target_dir.is_dir():
                logger.warning("Ingestion target directory does not exist: %s", target_dir)
                return Response(
                    {"error": f"Target directory does not exist: {target_dir.name}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pipeline = IngestionPipeline()
            report = pipeline.ingest_directory(target_dir)

            response_data = {
                "status": "success",
                "documents_processed": report["documents_processed"],
                "total_chunks": report["total_chunks"],
                "documents": report["documents"],
            }
            resp_serializer = IngestResponseSerializer(data=response_data)
            resp_serializer.is_valid(raise_exception=True)
            return Response(resp_serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            logger.warning("Ingest validation error: %s", str(e))
            return Response({"error": "Invalid ingestion request."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("DocumentIngestView failure: %s", str(e))
            return Response(
                {"error": "Unable to process document ingestion request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DocumentListView(APIView):
    """GET /api/documents/ - Returns list of ingested documents and chunk counts."""

    def get(self, request):
        logger.info("GET /api/documents/ requested")
        try:
            _ensure_auto_ingested()
            vector_store = ProviderRegistry.get_vector_store_provider()
            stats = vector_store.get_document_stats()

            serializer = DocumentStatsSerializer(data=stats)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("DocumentListView failure: %s", str(e))
            return Response(
                {"error": "Unable to retrieve document list."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChatView(APIView):
    """
    POST /api/chat/ - Primary customer support QA endpoint.
    Request: {"question": "What is the return policy?"}
    Response: {"answer": "...", "sources": [{"document": "...", "page": 1, "relevance": 0.91}]}
    """

    def post(self, request):
        logger.info("POST /api/chat/ requested")
        try:
            serializer = ChatQuerySerializer(data=request.data)
            if not serializer.is_valid():
                logger.warning("Chat validation error: %s", serializer.errors)
                return Response(
                    {"error": "Invalid request payload. 'question' field is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            _ensure_auto_ingested()

            question = serializer.validated_data["question"]
            top_k = serializer.validated_data.get("top_k", getattr(settings, "DEFAULT_TOP_K", 3))

            rag_pipeline = RAGPipeline()
            result = rag_pipeline.ask(question=question, top_k=top_k)

            resp_serializer = ChatResponseSerializer(data=result)
            resp_serializer.is_valid(raise_exception=True)
            return Response(resp_serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("ChatView failure: %s", str(e))
            return Response(
                {"error": "Unable to process your request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

