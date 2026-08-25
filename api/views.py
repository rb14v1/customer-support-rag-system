"""
Django REST Framework Views for Customer Support RAG System.
"""

import logging
from pathlib import Path

import pypdf
from django.conf import settings
from django.http import FileResponse
from mozilla_django_oidc.contrib.drf import OIDCAuthentication
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import (
    ChatQuerySerializer,
    ChatResponseSerializer,
    DocumentStatsSerializer,
    HealthCheckSerializer,
    IngestRequestSerializer,
    IngestResponseSerializer,
)
from rag.ingest import IngestionPipeline
from rag.rag import RAGPipeline
from rag.retrieve import ProviderRegistry


logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def get_data_directory():
    """
    Return the configured data directory.

    Uses DATA_DIR from Django settings if available.
    Otherwise defaults to <project_root>/data.
    """
    try:
        data_dir = Path(
            getattr(
                settings,
                "DATA_DIR",
                Path(settings.BASE_DIR) / "data",
            )
        )
        logger.debug("Resolved data directory: %s", data_dir)
        return data_dir
    except Exception:
        logger.exception("Failed to resolve data directory")
        return Path(getattr(settings, "BASE_DIR", ".")) / "data"


def get_vector_store():
    """
    Return the configured vector store provider.

    The actual provider is resolved through ProviderRegistry.
    """
    try:
        return ProviderRegistry.get_vector_store_provider()
    except Exception:
        logger.exception("Failed to get vector store provider from ProviderRegistry")
        raise


def get_vector_store_stats():
    """
    Return statistics from the configured vector store.
    """

    vector_store = get_vector_store()

    try:
        stats = vector_store.get_document_stats()

        if not isinstance(stats, dict):
            logger.warning(
                "Vector store returned unexpected stats format: %s",
                type(stats),
            )
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "documents": [],
            }

        return {
            "total_documents": stats.get(
                "total_documents",
                0,
            ),
            "total_chunks": stats.get(
                "total_chunks",
                0,
            ),
            "documents": stats.get(
                "documents",
                [],
            ),
        }

    except Exception:
        logger.exception(
            "Failed to retrieve vector store statistics"
        )
        raise


def ensure_auto_ingested():
    """
    Automatically ingest PDFs from DATA_DIR when the
    vector store is empty.

    This keeps the API convenient during development.
    """

    try:
        stats = get_vector_store_stats()

        total_chunks = stats.get(
            "total_chunks",
            0,
        )

        if total_chunks > 0:
            return

        data_dir = get_data_directory()

        if not data_dir.is_dir():
            logger.warning(
                "DATA_DIR does not exist: %s",
                data_dir,
            )
            return

        pdf_files = list(
            data_dir.glob("*.pdf")
        )

        if not pdf_files:
            logger.warning(
                "No PDF files found in DATA_DIR: %s",
                data_dir,
            )
            return

        logger.info(
            "Vector store is empty. "
            "Starting automatic ingestion from %s",
            data_dir,
        )

        pipeline = IngestionPipeline()

        pipeline.ingest_directory(
            data_dir
        )

        logger.info(
            "Automatic ingestion completed"
        )

    except Exception:
        logger.exception(
            "Automatic ingestion failed"
        )

        # Do not crash health checks/chat immediately.
        # The actual endpoint will handle retrieval errors.
        return


# ============================================================
# HEALTH CHECK
# ============================================================

class HealthCheckView(APIView):
    """
    GET /api/health/

    Returns system health and vector-store statistics.
    Public endpoint — no authentication required.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        logger.info(
            "GET /api/health/ requested"
        )

        try:
            ensure_auto_ingested()

            stats = get_vector_store_stats()

            vector_store = get_vector_store()

            data = {
                "status": "healthy",
                "documents_indexed": stats.get(
                    "total_documents",
                    0,
                ),
                "chunks_indexed": stats.get(
                    "total_chunks",
                    0,
                ),
                "vector_store_provider": (
                    vector_store.__class__.__name__
                ),
            }

            serializer = HealthCheckSerializer(
                data=data
            )

            serializer.is_valid(
                raise_exception=True
            )

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.exception(
                "HealthCheckView failed"
            )

            return Response(
                {
                    "error": (
                        "Unable to check system health."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ============================================================
# DOCUMENT INGESTION
# ============================================================

class DocumentIngestView(APIView):
    """
    POST /api/ingest/

    Ingests PDF documents from the configured data directory.

    Optional request:

    {
        "data_dir": "path/to/data"
    }
    """

    authentication_classes = [OIDCAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info(
            "POST /api/ingest/ requested"
        )

        try:
            serializer = IngestRequestSerializer(
                data=request.data
            )

            serializer.is_valid(
                raise_exception=True
            )

            custom_dir = serializer.validated_data.get(
                "data_dir"
            )

            if custom_dir:
                target_dir = Path(
                    custom_dir
                )
            else:
                target_dir = get_data_directory()

            target_dir = target_dir.resolve()

            if not target_dir.is_dir():
                logger.warning(
                    "Ingestion directory does not exist: %s",
                    target_dir,
                )

                return Response(
                    {
                        "error": (
                            "Target directory does not exist."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pdf_files = list(
                target_dir.glob("*.pdf")
            )

            if not pdf_files:
                return Response(
                    {
                        "error": (
                            "No PDF documents found "
                            "in the target directory."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pipeline = IngestionPipeline()

            report = pipeline.ingest_directory(
                target_dir
            )

            response_data = {
                "status": "success",
                "documents_processed": report.get(
                    "documents_processed",
                    0,
                ),
                "total_chunks": report.get(
                    "total_chunks",
                    0,
                ),
                "documents": report.get(
                    "documents",
                    [],
                ),
            }

            response_serializer = (
                IngestResponseSerializer(
                    data=response_data
                )
            )

            response_serializer.is_valid(
                raise_exception=True
            )

            return Response(
                response_serializer.data,
                status=status.HTTP_200_OK,
            )

        except ValidationError:
            logger.warning(
                "Invalid ingestion request"
            )

            return Response(
                {
                    "error": (
                        "Invalid ingestion request."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.exception(
                "DocumentIngestView failed"
            )

            return Response(
                {
                    "error": (
                        "Unable to process "
                        "document ingestion request."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ============================================================
# DOCUMENT LIST / STATISTICS
# ============================================================

class DocumentListView(APIView):
    """
    GET /api/documents/

    Returns information about indexed documents.
    """

    authentication_classes = [OIDCAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger.info(
            "GET /api/documents/ requested"
        )

        try:
            ensure_auto_ingested()

            stats = get_vector_store_stats()

            serializer = DocumentStatsSerializer(
                data=stats
            )

            serializer.is_valid(
                raise_exception=True
            )

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.exception(
                "DocumentListView failed"
            )

            return Response(
                {
                    "error": (
                        "Unable to retrieve "
                        "document list."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ============================================================
# CHAT
# ============================================================

class ChatView(APIView):
    """
    POST /api/chat/

    Request:

    {
        "question": "What is the return policy?",
        "top_k": 3,
        "conversation_history": []
    }

    Response:

    {
        "answer": "...",
        "sources": [...]
    }
    """

    authentication_classes = [OIDCAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info(
            "POST /api/chat/ requested"
        )

        try:
            serializer = ChatQuerySerializer(
                data=request.data
            )

            serializer.is_valid(
                raise_exception=True
            )

            question = serializer.validated_data[
                "question"
            ]

            top_k = serializer.validated_data.get(
                "top_k",
                getattr(
                    settings,
                    "DEFAULT_TOP_K",
                    3,
                ),
            )

            conversation_history = (
                serializer.validated_data.get(
                    "conversation_history",
                    [],
                )
            )

            # Make sure documents are available.
            ensure_auto_ingested()

            logger.info(
                "Processing question: %s",
                question,
            )

            rag_pipeline = RAGPipeline()

            result = rag_pipeline.ask(
                question=question,
                top_k=top_k,
                conversation_history=conversation_history,
            )

            if not isinstance(result, dict):
                logger.error(
                    "RAGPipeline returned unexpected type: %s",
                    type(result),
                )

                return Response(
                    {
                        "error": (
                            "Invalid response from "
                            "RAG pipeline."
                        )
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            answer = result.get(
                "answer",
                "",
            )

            sources = result.get(
                "sources",
                [],
            )

            # ------------------------------------------------
            # Normalize source information
            # ------------------------------------------------

            normalized_sources = []

            for source in sources:

                if not isinstance(
                    source,
                    dict,
                ):
                    continue

                document = source.get(
                    "document",
                    source.get(
                        "file_name",
                        source.get(
                            "document_name",
                            "",
                        ),
                    ),
                )

                page = source.get(
                    "page",
                    source.get(
                        "page_number",
                        1,
                    ),
                )

                relevance = source.get(
                    "relevance",
                    source.get(
                        "score",
                        0.0,
                    ),
                )

                chunk_id = source.get(
                    "chunk_id",
                    source.get(
                        "id",
                        "",
                    ),
                )

                text = source.get(
                    "text",
                    source.get(
                        "content",
                        "",
                    ),
                )

                try:
                    page = int(page)
                except (
                    TypeError,
                    ValueError,
                ):
                    page = 1

                try:
                    relevance = float(
                        relevance or 0.0
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    relevance = 0.0

                title = source.get(
                    "title",
                    "",
                )

                if not title and document:
                    title = (
                        document
                        .replace(
                            "_",
                            " ",
                        )
                        .replace(
                            ".pdf",
                            "",
                        )
                        .title()
                    )

                # URL points to the local PDF source
                # endpoint.
                url = source.get(
                    "url",
                    "",
                )

                if not url and document:
                    url = (
                        f"/api/documents/"
                        f"{document}/source/"
                        f"?page={page}"
                        f"#page={page}"
                    )

                normalized_sources.append(
                    {
                        "document": document,
                        "page": page,
                        "relevance": relevance,
                        "chunk_id": chunk_id,
                        "text": text,
                        "url": url,
                        "title": title,
                    }
                )

            response_data = {
                "answer": answer,
                "sources": normalized_sources,
            }

            response_serializer = (
                ChatResponseSerializer(
                    data=response_data
                )
            )

            response_serializer.is_valid(
                raise_exception=True
            )

            return Response(
                response_serializer.data,
                status=status.HTTP_200_OK,
            )

        except ValidationError:
            logger.warning(
                "Chat request validation failed"
            )

            return Response(
                {
                    "error": (
                        "Invalid request payload. "
                        "'question' field is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.exception(
                "ChatView failed"
            )

            return Response(
                {
                    "error": (
                        "Unable to process "
                        "your request."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ============================================================
# DOCUMENT SOURCE
# ============================================================

class DocumentSourceView(APIView):
    """
    GET /api/documents/<document_name>/source/?page=1

    Serves a PDF from DATA_DIR.

    Security:
    - Only PDF files are allowed.
    - Directory traversal is blocked.
    - The resolved file must remain inside DATA_DIR.
    - Requested page number is validated.
    """

    authentication_classes = [OIDCAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(
        self,
        request,
        document_name,
    ):
        logger.info(
            "GET /api/documents/%s/source/ requested",
            document_name,
        )

        # ----------------------------------------------------
        # Validate document name
        # ----------------------------------------------------

        if not document_name:
            return Response(
                {
                    "error": (
                        "Document name is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            "/" in document_name
            or "\\" in document_name
            or ".." in document_name
        ):
            logger.warning(
                "Path traversal attempt blocked: %s",
                document_name,
            )

            return Response(
                {
                    "error": (
                        "Invalid document name."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # Validate extension
        # ----------------------------------------------------

        if not document_name.lower().endswith(
            ".pdf"
        ):
            return Response(
                {
                    "error": (
                        "Invalid file type. "
                        "Only PDF documents are allowed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # Resolve DATA_DIR
        # ----------------------------------------------------

        data_dir = get_data_directory().resolve()

        file_path = (
            data_dir / document_name
        ).resolve()

        # ----------------------------------------------------
        # Containment check
        # ----------------------------------------------------

        try:
            file_path.relative_to(
                data_dir
            )
        except ValueError:

            logger.warning(
                "Attempt to access file outside DATA_DIR: %s",
                document_name,
            )

            return Response(
                {
                    "error": "Access denied."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # Check file existence
        # ----------------------------------------------------

        if not file_path.is_file():
            logger.warning(
                "Document not found: %s",
                document_name,
            )

            return Response(
                {
                    "error": (
                        f"Document "
                        f"'{document_name}' "
                        f"not found."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ----------------------------------------------------
        # Validate page number
        # ----------------------------------------------------

        page_param = request.query_params.get(
            "page",
            "1",
        )

        try:
            page_num = int(
                page_param
            )
        except (
            ValueError,
            TypeError,
        ):

            return Response(
                {
                    "error": (
                        "Page number must "
                        "be an integer."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if page_num < 1:
            return Response(
                {
                    "error": (
                        "Page number must "
                        "be a positive integer."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # Validate PDF page count
        # ----------------------------------------------------

        try:
            reader = pypdf.PdfReader(
                str(file_path)
            )

            total_pages = len(
                reader.pages
            )

        except Exception:
            logger.exception(
                "Failed to inspect PDF: %s",
                document_name,
            )

            return Response(
                {
                    "error": (
                        "Unable to inspect "
                        "PDF document."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if page_num > total_pages:
            return Response(
                {
                    "error": (
                        f"Page number {page_num} "
                        f"exceeds document total "
                        f"pages ({total_pages})."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # Serve PDF
        # ----------------------------------------------------

        try:
            response = FileResponse(
                open(
                    file_path,
                    "rb",
                ),
                content_type="application/pdf",
            )

            response[
                "Content-Disposition"
            ] = (
                f'inline; '
                f'filename="{document_name}"'
            )

            return response

        except Exception:
            logger.exception(
                "Failed to serve PDF: %s",
                document_name,
            )

            return Response(
                {
                    "error": (
                        "Unable to serve "
                        "PDF document."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )