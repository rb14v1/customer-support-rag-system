from pathlib import Path
import shutil

from fastapi import FastAPI
from fastapi import UploadFile
from fastapi import File
from fastapi import HTTPException

from pydantic import BaseModel

from ingest import ingest_document
from ingest import ingest_all_documents
from rag import ask_rag

app = FastAPI(
    title="Azure Customer Support RAG API",
    version="1.0"
)

UPLOAD_FOLDER = "data"

Path(UPLOAD_FOLDER).mkdir(exist_ok=True)


class ChatRequest(BaseModel):
    question: str


@app.get("/")
def home():
    return {
        "message": "Azure Customer Support RAG API is running."
    }


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload and immediately index a PDF."""

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    file_path = Path(UPLOAD_FOLDER) / file.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    chunks = ingest_document(str(file_path))

    return {
        "message": f"{file.filename} uploaded successfully.",
        "chunks_indexed": chunks
    }


@app.post("/ingest")
def ingest_documents():
    """Index all PDFs inside the data folder."""

    total = ingest_all_documents()

    return {
        "message": "All documents indexed successfully.",
        "total_chunks": total
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """Ask questions to the RAG system."""

    answer = ask_rag(request.question)

    return {
        "question": request.question,
        "answer": answer
    }