"""
PDF Ingestion and Document Chunking Module.
Extracts text from PDF files, chunks them into configurable segments with page metadata,
and feeds them to the configured VectorStoreProvider via ProviderRegistry.
"""
import uuid
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pypdf

from rag.retrieve import DocumentChunk, ProviderRegistry, AbstractVectorStoreProvider

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extracts text content per page from PDF documents."""

    @staticmethod
    def extract_pages(pdf_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Reads a PDF file and returns a list of page dicts:
        [{"page_number": 1, "text": "..."}, ...]
        """
        path = Path(pdf_path)
        logger.info("Starting extract_pages for PDF path: %s", path)
        if not path.is_file():
            logger.error("PDF file not found at path: %s", path)
            raise FileNotFoundError(f"PDF file not found: {path}")

        logger.info("Extracting text pages from PDF: %s", path.name)
        pages: List[Dict[str, Any]] = []
        try:
            reader = pypdf.PdfReader(str(path))
            for idx, page in enumerate(reader.pages):
                extracted = page.extract_text() or ""
                text = extracted.strip()
                if text:
                    pages.append({
                        "page_number": idx + 1,
                        "text": text,
                    })
            logger.info("Successfully extracted %d non-empty pages from %s", len(pages), path.name)
        except (pypdf.errors.PyPdfError, OSError) as e:
            logger.error("Failed to parse PDF file %s: %s", path.name, str(e))
            raise RuntimeError(f"Error parsing PDF file {path.name}: {str(e)}") from e
        except Exception as e:
            logger.exception("Unexpected error extracting PDF file %s: %s", path.name, str(e))
            raise RuntimeError(f"Unexpected error reading PDF file {path.name}: {str(e)}") from e
        finally:
            logger.info("Finished extract_pages for PDF path: %s", path)

        return pages


class DocumentChunker:
    """Splits document page text into smaller overlapping text chunks."""

    def __init__(self, chunk_size: int = 700, chunk_overlap: int = 100):
        logger.info("Starting DocumentChunker initialization (chunk_size=%s, chunk_overlap=%s)", chunk_size, chunk_overlap)
        try:
            if chunk_size <= 0:
                raise ValueError("chunk_size must be a positive integer.")
            if chunk_overlap < 0 or chunk_overlap >= chunk_size:
                raise ValueError("chunk_overlap must be non-negative and less than chunk_size.")
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
            logger.info("Finished DocumentChunker initialization")
        except Exception:
            logger.exception("Failed to initialize DocumentChunker (chunk_size=%s, chunk_overlap=%s)", chunk_size, chunk_overlap)
            raise

    def chunk_page(self, document_name: str, page_number: int, page_text: str) -> List[DocumentChunk]:
        logger.info("Starting chunk_page for doc: %s, page: %d", document_name, page_number)
        try:
            if not page_text or not page_text.strip():
                logger.info("Finished chunk_page for doc: %s, page: %d (empty page_text)", document_name, page_number)
                return []

            chunks: List[DocumentChunk] = []
            start = 0
            text_len = len(page_text)
            chunk_idx = 1

            step = max(1, self.chunk_size - self.chunk_overlap)

            while start < text_len:
                end = start + self.chunk_size
                chunk_text = page_text[start:end].strip()

                if chunk_text:
                    chunk_id = str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            f"{document_name}_p{page_number}_c{chunk_idx}"
                        )
                    )

                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            text=chunk_text,
                            document_name=document_name,
                            page_number=page_number,
                            metadata={
                                "char_length": len(chunk_text),
                                "chunk_index": chunk_idx,
                                "original_chunk_id": (
                                    f"{document_name}_p{page_number}_c{chunk_idx}"
                                ),
                            },
                        )
                    )
                    chunk_idx += 1

                start += step

            logger.info("Finished chunk_page for doc: %s, page: %d, produced %d chunks", document_name, page_number, len(chunks))
            return chunks
        except Exception as e:
            logger.exception("Failed to chunk page %d of document %s: %s", page_number, document_name, str(e))
            raise RuntimeError(f"Failed to chunk page {page_number} of document {document_name}: {str(e)}") from e

    def chunk_document(self, document_name: str, pages: List[Dict[str, Any]]) -> List[DocumentChunk]:
        logger.info("Starting chunk_document for doc: %s", document_name)
        all_chunks: List[DocumentChunk] = []
        try:
            for p in pages:
                chunks = self.chunk_page(
                    document_name=document_name,
                    page_number=p["page_number"],
                    page_text=p["text"],
                )
                all_chunks.extend(chunks)
            logger.info("Chunked document %s into %d total chunks", document_name, len(all_chunks))
        except Exception as e:
            logger.exception("Error chunking document %s: %s", document_name, str(e))
            raise RuntimeError(f"Error chunking document {document_name}: {str(e)}") from e
        finally:
            logger.info("Finished chunk_document for doc: %s", document_name)

        return all_chunks


class IngestionPipeline:
    """Pipeline to load PDFs, chunk them, and index into VectorStoreProvider."""

    def __init__(
        self,
        vector_store_provider: Optional[AbstractVectorStoreProvider] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        logger.info("Starting IngestionPipeline initialization")
        try:
            self._vector_store = vector_store_provider
            self.chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            logger.info("Finished IngestionPipeline initialization")
        except Exception:
            logger.exception("Failed to initialize IngestionPipeline")
            raise

    @property
    def vector_store(self) -> AbstractVectorStoreProvider:
        logger.debug("Starting vector_store resolution in IngestionPipeline")
        try:
            if self._vector_store is not None:
                logger.debug("Finished vector_store resolution in IngestionPipeline (explicit)")
                return self._vector_store
            res = ProviderRegistry.get_vector_store_provider()
            logger.debug("Finished vector_store resolution in IngestionPipeline (registry)")
            return res
        except Exception:
            logger.exception("Failed to resolve vector store provider in IngestionPipeline")
            raise

    def ingest_pdf(self, pdf_path: Union[str, Path]) -> List[DocumentChunk]:
        path = Path(pdf_path)
        logger.info("Starting ingest_pdf of PDF: %s", path.name)
        try:
            if os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
                try:
                    from azure_services.azure_config import get_blob_container_client
                    from azure_services.blob_service import upload_blob

                    container_client = get_blob_container_client()
                    upload_blob(container_client, str(path), path.name)
                    logger.info("Uploaded %s to Azure Blob Storage container", path.name)
                except Exception as blob_err:
                    logger.warning("Failed to upload %s to Azure Blob Storage: %s", path.name, str(blob_err))

            pages = PDFExtractor.extract_pages(path)
            chunks = self.chunker.chunk_document(path.name, pages)
            if chunks:
                indexed_count = self.vector_store.index_chunks(chunks)
                logger.info("Indexed %d chunks for PDF %s into vector store", indexed_count, path.name)
            else:
                logger.warning("No text chunks generated for PDF %s", path.name)
            return chunks
        except Exception as e:
            logger.error("Ingestion failed for PDF %s: %s", path.name, str(e))
            raise
        finally:
            logger.info("Finished ingest_pdf for PDF: %s", path.name)

    def ingest_directory(self, data_dir: Union[str, Path]) -> Dict[str, Any]:
        target_dir = Path(data_dir)
        logger.info("Starting ingest_directory for path: %s", target_dir)
        if not target_dir.is_dir():
            logger.error("Target ingestion directory not found: %s", target_dir)
            raise FileNotFoundError(f"Directory not found: {target_dir}")

        pdf_files = sorted(list(target_dir.glob("*.pdf")))
        logger.info("Found %d PDF file(s) in %s for ingestion", len(pdf_files), target_dir)
        processed_docs: List[str] = []

        try:
            for pdf_path in pdf_files:
                try:
                    self.ingest_pdf(pdf_path)
                    processed_docs.append(pdf_path.name)
                except Exception as e:
                    logger.warning("Skipping failed PDF %s during batch ingestion: %s", pdf_path.name, str(e))

            stats = self.vector_store.get_document_stats()
            logger.info("Batch ingestion finished. Processed %d documents. Vector store stats: %s", len(processed_docs), stats)

            return {
                "documents_processed": len(processed_docs),
                "total_chunks": stats.get("total_chunks", 0),
                "documents": processed_docs,
            }
        finally:
            logger.info("Finished ingest_directory for path: %s", target_dir)
