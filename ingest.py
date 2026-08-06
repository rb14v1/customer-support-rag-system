from pathlib import Path
from PyPDF2 import PdfReader

from azure_config import get_embedding_client
from search_service import upload_documents

CHUNK_SIZE = 500
OVERLAP = 50


def read_pdf(file_path: str):
    """Read text from a PDF file."""
    reader = PdfReader(file_path)
    text = ""

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text


def chunk_text(text):
    """Split text into overlapping chunks."""
    chunks = []
    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - OVERLAP

    return chunks


def generate_embedding(text):
    """Generate embedding using Azure OpenAI."""
    client = get_embedding_client()

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )

    return response.data[0].embedding


def ingest_document(file_path):
    """Read, chunk, embed and upload a single document."""

    print(f"\nProcessing: {file_path}")

    text = read_pdf(file_path)

    chunks = chunk_text(text)

    docs = []

    for i, chunk in enumerate(chunks):

        embedding = generate_embedding(chunk)

        docs.append(
            {
                "id": f"{Path(file_path).stem}_{i}",
                "content": chunk,
                "embedding": embedding
            }
        )

    upload_documents(docs)

    print(f"Indexed {len(docs)} chunks")

    return len(docs)


def ingest_all_documents():
    """Index every PDF in the data folder."""

    folder = Path("data")

    if not folder.exists():
        raise FileNotFoundError("data folder not found.")

    total_chunks = 0

    pdf_files = list(folder.glob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError("No PDF files found in data folder.")

    print(f"\nFound {len(pdf_files)} PDF files.\n")

    for pdf in pdf_files:
        total_chunks += ingest_document(str(pdf))

    print("\n=================================")
    print(f"Indexed {len(pdf_files)} documents")
    print(f"Total chunks: {total_chunks}")
    print("=================================\n")

    return total_chunks