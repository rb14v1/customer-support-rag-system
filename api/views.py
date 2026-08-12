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
    Response: {"answer": "...", "sources": [{"document": "...", "page": 1, "relevance": 0.91, "chunk_id": "...", "text": "..."}]}
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

            # Enrich sources with source URL and page fragment anchor
            for src in result.get("sources", []):
                doc_name = src.get("document", "")
                page_num = src.get("page", 1)
                if "url" not in src or not src["url"]:
                    src["url"] = f"/api/documents/{doc_name}/source/?page={page_num}#page={page_num}"
                if "title" not in src or not src["title"]:
                    src["title"] = doc_name.replace("_", " ").replace(".pdf", "").title()

            resp_serializer = ChatResponseSerializer(data=result)
            resp_serializer.is_valid(raise_exception=True)
            return Response(resp_serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("ChatView failure: %s", str(e))
            return Response(
                {"error": "Unable to process your request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


from django.http import FileResponse
import pypdf


class DocumentSourceView(APIView):
    """
    GET /api/documents/<document_name>/source/?page=1
    Serves requested PDF file securely from settings.DATA_DIR.
    Validates file type, page existence, and prevents path traversal attacks.
    """

    def get(self, request, document_name):
        logger.info("GET /api/documents/%s/source/ requested", document_name)

        # 1. Reject path traversal, directory separators, and parent references
        if not document_name or "/" in document_name or "\\" in document_name or ".." in document_name:
            logger.warning("Path traversal attempt blocked: %s", document_name)
            return Response(
                {"error": "Invalid document name. Path traversal is strictly prohibited."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Only allow .pdf extension
        if not document_name.lower().endswith(".pdf"):
            logger.warning("Non-PDF document requested: %s", document_name)
            return Response(
                {"error": "Invalid file type. Only PDF documents can be accessed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Locate file inside settings.DATA_DIR
        data_dir = Path(getattr(settings, "DATA_DIR", Path(settings.BASE_DIR) / "data")).resolve()
        file_path = (data_dir / document_name).resolve()

        # Containment check
        try:
            file_path.relative_to(data_dir)
        except ValueError:
            logger.warning("File outside DATA_DIR requested: %s", document_name)
            return Response(
                {"error": "Access denied."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not file_path.is_file():
            logger.warning("Requested document not found: %s", document_name)
            return Response(
                {"error": f"Document '{document_name}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 4. Validate page number parameter
        page_param = request.query_params.get("page", 1)
        try:
            page_num = int(page_param)
        except (ValueError, TypeError):
            logger.warning("Invalid page parameter: %s", page_param)
            return Response(
                {"error": "Page number must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if page_num < 1:
            logger.warning("Page number < 1 requested: %d", page_num)
            return Response(
                {"error": "Page number must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reader = pypdf.PdfReader(str(file_path))
            total_pages = len(reader.pages)
            if page_num > total_pages:
                logger.warning("Page number %d exceeds total pages %d in %s", page_num, total_pages, document_name)
                return Response(
                    {"error": f"Page number {page_num} exceeds document total pages ({total_pages})."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            logger.exception("Error validating PDF page count for %s: %s", document_name, str(e))
            return Response(
                {"error": "Error inspecting PDF document."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            response = FileResponse(open(file_path, "rb"), content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{document_name}"'
            return response
        except Exception as e:
            logger.exception("Error serving PDF file %s: %s", document_name, str(e))
            return Response(
                {"error": "Unable to serve PDF document."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
