"""
RAG pipeline for the Customer Support system.

Responsibilities:
1. Retrieve relevant document chunks.
2. Build a context from retrieved chunks.
3. Generate an answer using Azure OpenAI.
4. Return the answer together with source citations.

Compatible with:
    rag.retrieve
    api.views
"""

import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from azure_services.azure_config import get_openai_client
from rag.retrieve import ProviderRegistry

load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_CHAT_DEPLOYMENT"
)

DEFAULT_TOP_K = int(
    os.getenv("DEFAULT_TOP_K", "3")
)


# ============================================================
# RAG PIPELINE
# ============================================================

class RAGPipeline:
    """
    Complete Retrieval-Augmented Generation pipeline.

    Flow:

        User Question
              |
              v
        ProviderRegistry
              |
              v
        Hybrid Search
        /           \
       v             v
    Azure AI       Qdrant
      Search
       \             /
        v           v
        Search Results
              |
              v
        Build Context
              |
              v
        Azure OpenAI
              |
              v
        Final Answer + Sources
    """

    def __init__(self):
        logger.info("Initializing RAG pipeline")

        self.openai_client = get_openai_client()

        if not AZURE_OPENAI_CHAT_DEPLOYMENT:
            raise ValueError(
                "AZURE_OPENAI_CHAT_DEPLOYMENT "
                "is not configured."
            )

        self.vector_store = (
            ProviderRegistry.get_vector_store_provider()
        )

    # ========================================================
    # CONVERT SEARCH RESULTS
    # ========================================================

    def _convert_search_results(
        self,
        search_results: List[Any],
    ) -> List[Dict[str, Any]]:
        """
        Convert SearchResult dataclass objects returned by
        retrieve.py into dictionaries used by this RAG layer.
        """

        documents = []

        for result in search_results:

            documents.append(
                {
                    "chunk_id": str(
                        result.chunk_id
                    ),
                    "text": str(
                        result.text
                    ),
                    "content": str(
                        result.text
                    ),
                    "document": str(
                        result.document_name
                    ),
                    "document_name": str(
                        result.document_name
                    ),
                    "page": int(
                        result.page_number
                    ),
                    "page_number": int(
                        result.page_number
                    ),
                    "relevance": float(
                        result.relevance
                    ),
                    "metadata": (
                        result.metadata
                        if result.metadata
                        else {}
                    ),
                }
            )

        return documents

    # ========================================================
    # BUILD CONTEXT
    # ========================================================

    def build_context(
        self,
        documents: List[Dict[str, Any]],
    ) -> str:
        """
        Convert retrieved documents into a context string.
        """

        context_parts = []

        for document in documents:

            content = document.get(
                "content",
                "",
            )

            if not content:
                content = document.get(
                    "text",
                    "",
                )

            if not content:
                continue

            document_name = document.get(
                "document",
                document.get(
                    "document_name",
                    "Unknown source",
                ),
            )

            page_number = document.get(
                "page",
                document.get(
                    "page_number",
                    1,
                ),
            )

            relevance = document.get(
                "relevance",
                0.0,
            )

            context_parts.append(
                f"Source: {document_name}\n"
                f"Page: {page_number}\n"
                f"Relevance: {relevance:.4f}\n"
                f"{content}"
            )

        return "\n\n---\n\n".join(
            context_parts
        )

    # ========================================================
    # BUILD CONVERSATION HISTORY
    # ========================================================

    def build_conversation_history(
        self,
        conversation_history: Optional[
            List[Dict[str, str]]
        ] = None,
    ) -> List[Dict[str, str]]:
        """
        Convert previous conversation messages into
        Azure OpenAI chat messages.
        """

        if not conversation_history:
            return []

        messages = []

        for message in conversation_history:

            role = message.get(
                "role"
            )

            content = message.get(
                "content",
                "",
            )

            if role not in {
                "user",
                "assistant",
            }:
                continue

            if not content:
                continue

            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        return messages

    # ========================================================
    # BUILD PROMPT
    # ========================================================

    def build_prompt(
        self,
        question: str,
        context: str,
    ) -> str:
        """
        Build the prompt sent to Azure OpenAI.
        """

        return f"""
You are a helpful customer support assistant.

Answer the user's question using ONLY the information
provided in the knowledge-base context below.

Rules:
- Do not invent information.
- Do not make up policies, prices, dates, or procedures.
- If the answer cannot be found in the context, clearly
  say that you do not have enough information.
- Keep the answer clear, concise, and helpful.
- Do not rely on outside knowledge.
- When possible, mention the relevant policy or document
  name in your answer.

Knowledge Base Context:
-------------------------
{context}
-------------------------

User Question:
{question}

Answer:
"""

    # ========================================================
    # GENERATE ANSWER
    # ========================================================

    def generate_answer(
        self,
        question: str,
        context: str,
        conversation_history: Optional[
            List[Dict[str, str]]
        ] = None,
    ) -> str:
        """
        Generate the final answer using Azure OpenAI.
        """

        prompt = self.build_prompt(
            question=question,
            context=context,
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a customer support assistant. "
                    "Answer questions using only the "
                    "provided knowledge-base context. "
                    "Never invent information."
                ),
            }
        ]

        messages.extend(
            self.build_conversation_history(
                conversation_history
            )
        )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        logger.info(
            "Generating answer using Azure OpenAI"
        )

        try:
            response = (
                self.openai_client
                .chat.completions.create(
                    model=AZURE_OPENAI_CHAT_DEPLOYMENT,
                    messages=messages,
                    temperature=0.2,
                )
            )

        except Exception:
            logger.exception(
                "Azure OpenAI answer generation failed"
            )
            raise

        if not response.choices:
            raise RuntimeError(
                "Azure OpenAI returned no response choices."
            )

        answer = (
            response.choices[0]
            .message.content
        )

        if not answer:
            raise RuntimeError(
                "Azure OpenAI returned an empty answer."
            )

        return answer.strip()

    # ========================================================
    # BUILD SOURCES
    # ========================================================

    def build_sources(
        self,
        documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Convert retrieved documents into the source format
        expected by ChatResponseSerializer.
        """

        sources = []

        for document in documents:

            document_name = document.get(
                "document",
                document.get(
                    "document_name",
                    "Unknown source",
                ),
            )

            page_number = document.get(
                "page",
                document.get(
                    "page_number",
                    1,
                ),
            )

            relevance = document.get(
                "relevance",
                document.get(
                    "score",
                    0.0,
                ),
            )

            chunk_id = document.get(
                "chunk_id",
                "",
            )

            text = document.get(
                "text",
                document.get(
                    "content",
                    "",
                ),
            )

            sources.append(
                {
                    "document": str(
                        document_name
                    ),
                    "page": int(
                        page_number
                    ),
                    "relevance": float(
                        relevance
                    ),
                    "chunk_id": str(
                        chunk_id
                    ),
                    "text": str(
                        text
                    ),
                    "url": "",
                    "title": "",
                }
            )

        return sources

    # ========================================================
    # MAIN RAG METHOD
    # ========================================================

    def ask(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        conversation_history: Optional[
            List[Dict[str, str]]
        ] = None,
    ) -> Dict[str, Any]:
        """
        Execute the complete RAG pipeline.

        Returns:

        {
            "answer": "...",
            "sources": [...]
        }
        """

        if not question or not question.strip():
            raise ValueError(
                "Question cannot be empty."
            )

        question = question.strip()

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero."
            )

        logger.info(
            "Processing customer question: %s",
            question,
        )

        # ----------------------------------------------------
        # 1. RETRIEVE RELEVANT DOCUMENTS
        # ----------------------------------------------------

        logger.info(
            "Searching for top %d relevant chunks",
            top_k,
        )

        search_results = (
            self.vector_store.search(
                query=question,
                top_k=top_k,
            )
        )

        documents = (
            self._convert_search_results(
                search_results
            )
        )

        if not documents:

            logger.warning(
                "No relevant documents found."
            )

            return {
                "answer": (
                    "I couldn't find enough information "
                    "in the knowledge base to answer "
                    "your question."
                ),
                "sources": [],
            }

        logger.info(
            "Retrieved %d relevant documents",
            len(documents),
        )

        # ----------------------------------------------------
        # 2. BUILD CONTEXT
        # ----------------------------------------------------

        context = self.build_context(
            documents
        )

        if not context:

            logger.warning(
                "Retrieved documents contained "
                "no usable text."
            )

            return {
                "answer": (
                    "I couldn't find enough information "
                    "in the knowledge base to answer "
                    "your question."
                ),
                "sources": [],
            }

        # ----------------------------------------------------
        # 3. GENERATE ANSWER
        # ----------------------------------------------------

        answer = self.generate_answer(
            question=question,
            context=context,
            conversation_history=(
                conversation_history
            ),
        )

        # ----------------------------------------------------
        # 4. BUILD SOURCE CITATIONS
        # ----------------------------------------------------

        sources = self.build_sources(
            documents
        )

        logger.info(
            "RAG response generated successfully"
        )

        return {
            "answer": answer,
            "sources": sources,
        }


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def answer_question(
    question: str,
    top_k: int = DEFAULT_TOP_K,
) -> str:
    """
    Convenience function for callers that only need
    the generated answer.
    """

    pipeline = RAGPipeline()

    result = pipeline.ask(
        question=question,
        top_k=top_k,
    )

    return result["answer"]