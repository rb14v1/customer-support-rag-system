"""
PDF Ingestion and Document Chunking Module.
Extracts text from PDF files, chunks them into configurable segments with page metadata,
and feeds them to the configured VectorStoreProvider via ProviderRegistry.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Union
import pypdf

from rag.retrieve import DocumentChunk, ProviderRegistry, AbstractVectorStoreProvider


class PDFExtractor:
    """Extracts text content per page from PDF documents."""

    @staticmethod
    def extract_pages(pdf_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Reads a PDF file and returns a list of page dicts:
        [{"page_number": 1, "text": "..."}, ...]
        """
        path = Path(pdf_path)
        if not path.is_file():
            raise FileNotFoundError(f"PDF file not found: {path}")

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
        except Exception as e:
            # Fallback or re-raise with clear message
            raise RuntimeError(f"Error reading PDF file {path.name}: {str(e)}") from e

        return pages


class DocumentChunker:
    """Splits document page text into smaller overlapping text chunks."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_page(self, document_name: str, page_number: int, page_text: str) -> List[DocumentChunk]:
        if not page_text:
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
                chunk_id = f"{document_name}_p{page_number}_c{chunk_idx}"
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        text=chunk_text,
                        document_name=document_name,
                        page_number=page_number,
                        metadata={
                            "char_length": len(chunk_text),
                            "chunk_index": chunk_idx,
                        },
                    )
                )
                chunk_idx += 1

            start += step

        return chunks

    def chunk_document(self, document_name: str, pages: List[Dict[str, Any]]) -> List[DocumentChunk]:
        all_chunks: List[DocumentChunk] = []
        for p in pages:
            chunks = self.chunk_page(
                document_name=document_name,
                page_number=p["page_number"],
                page_text=p["text"],
            )
            all_chunks.extend(chunks)
        return all_chunks


class IngestionPipeline:
    """Pipeline to load PDFs, chunk them, and index into VectorStoreProvider."""

    def __init__(
        self,
        vector_store_provider: Optional[AbstractVectorStoreProvider] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self._vector_store = vector_store_provider
        self.chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    @property
    def vector_store(self) -> AbstractVectorStoreProvider:
        if self._vector_store is not None:
            return self._vector_store
        return ProviderRegistry.get_vector_store_provider()

    def ingest_pdf(self, pdf_path: Union[str, Path]) -> List[DocumentChunk]:
        path = Path(pdf_path)
        pages = PDFExtractor.extract_pages(path)
        chunks = self.chunker.chunk_document(path.name, pages)
        if chunks:
            self.vector_store.index_chunks(chunks)
        return chunks

    def ingest_directory(self, data_dir: Union[str, Path]) -> Dict[str, Any]:
        target_dir = Path(data_dir)
        if not target_dir.is_dir():
            raise FileNotFoundError(f"Directory not found: {target_dir}")

        pdf_files = sorted(list(target_dir.glob("*.pdf")))
        processed_docs: List[str] = []
        total_chunks_indexed = 0

        for pdf_path in pdf_files:
            self.ingest_pdf(pdf_path)
            processed_docs.append(pdf_path.name)

        stats = self.vector_store.get_document_stats()

        return {
            "documents_processed": len(processed_docs),
            "total_chunks": stats.get("total_chunks", 0),
            "documents": processed_docs,
        }
