"""
RAG Application Logic & Orchestration Module.
Constructs prompts, interfaces with LLM providers, and applies threshold filtering on retrieval relevance scores.
"""

import logging
from typing import Any, Dict, List, Optional
from rag.retrieve import (
    AbstractLLMProvider,
    AbstractVectorStoreProvider,
    ProviderRegistry,
    SearchResult,
)

logger = logging.getLogger(__name__)

try:
    from django.conf import settings
except ImportError:
    settings = None

DEFAULT_FALLBACK_MIN_RELEVANCE_SCORE = 0.30
FALLBACK_RESPONSE_TEXT = (
    "I couldn't find information about that in the customer support knowledge base. "
    "I can help with questions about our products, shipping, returns, refunds, warranty, troubleshooting, and account management."
)


class PromptBuilder:
    """Constructs context-grounded system and user prompts for RAG response generation."""

    @staticmethod
    def build_prompt(query: str, search_results: List[SearchResult]) -> str:
        if not search_results:
            logger.info("PromptBuilder received empty search_results for query: '%s'", query)
            return f"User Question: {query}\n\nNo relevant context was found in the knowledge base."

        context_blocks = []
        for idx, res in enumerate(search_results, 1):
            context_blocks.append(
                f"[{idx}] Source: Document '{res.document_name}', Page {res.page_number} (Relevance: {res.relevance:.2f})\n"
                f"Content: {res.text}"
            )

        context_str = "\n\n".join(context_blocks)
        prompt = (
            "You are a helpful and accurate customer support assistant.\n"
            "Answer the user's question strictly based on the provided context below. "
            "If the context does not contain sufficient information to answer, state that you do not have enough information.\n\n"
            f"--- CONTEXT START ---\n{context_str}\n--- CONTEXT END ---\n\n"
            f"User Question: {query}\n\n"
            "Answer:"
        )
        return prompt


class MockLLMProvider(AbstractLLMProvider):
    """
    Default mock LLM provider for local testing and offline development.
    Generates structured, grounded responses using retrieved search results.
    """

    def generate_response(self, prompt: str, search_results: List[SearchResult]) -> str:
        if not search_results:
            logger.info("MockLLMProvider returning fallback text due to empty search_results")
            return FALLBACK_RESPONSE_TEXT

        top_result = search_results[0]
        extracted_snippets = [r.text for r in search_results[:2]]
        combined_text = " ".join(extracted_snippets)

        if len(combined_text) > 400:
            summary = combined_text[:400].rsplit(".", 1)[0] + "."
        else:
            summary = combined_text

        answer = (
            f"{summary}\n\n"
            f"This information is referenced from {top_result.document_name} (Page {top_result.page_number})."
        )
        return answer


class RAGPipeline:
    """
    RAG Pipeline orchestrator for executing retrieval, prompt construction, and response synthesis.
    Applies configurable minimum relevance filtering.
    """

    def __init__(
        self,
        vector_store_provider: Optional[AbstractVectorStoreProvider] = None,
        llm_provider: Optional[AbstractLLMProvider] = None,
        min_relevance_score: Optional[float] = None,
    ):
        self._vector_store = vector_store_provider
        self._llm_provider = llm_provider
        self.min_relevance_score = min_relevance_score

    @property
    def vector_store(self) -> AbstractVectorStoreProvider:
        if self._vector_store is not None:
            return self._vector_store
        return ProviderRegistry.get_vector_store_provider()

    @property
    def llm_provider(self) -> AbstractLLMProvider:
        if self._llm_provider is not None:
            return self._llm_provider
        return ProviderRegistry.get_llm_provider()

    def get_min_relevance_score(self) -> float:
        if self.min_relevance_score is not None:
            return self.min_relevance_score
        if settings and hasattr(settings, "RAG_MIN_RELEVANCE_SCORE"):
            try:
                return float(getattr(settings, "RAG_MIN_RELEVANCE_SCORE"))
            except (ValueError, TypeError) as e:
                logger.warning("Failed to parse RAG_MIN_RELEVANCE_SCORE from settings: %s", str(e))
        return DEFAULT_FALLBACK_MIN_RELEVANCE_SCORE

    def ask(self, question: str, top_k: int = 3, min_relevance_score: Optional[float] = None) -> Dict[str, Any]:
        """
        Main customer support QA method.
        Filters retrieved search results by minimum relevance score threshold.
        Returns exact dictionary schema:
        {
            "answer": str,
            "sources": [
                {
                    "document": str,
                    "page": int,
                    "relevance": float
                }
            ]
        }
        """
        if not question or not isinstance(question, str) or not question.strip():
            logger.warning("RAGPipeline received empty or non-string question")
            return {
                "answer": "Please provide a non-empty question.",
                "sources": [],
            }

        question_clean = question.strip()
        effective_threshold = (
            min_relevance_score if min_relevance_score is not None else self.get_min_relevance_score()
        )

        logger.info("Processing RAG query: '%s' (top_k=%d, threshold=%.2f)", question_clean, top_k, effective_threshold)

        try:
            # 1. Retrieve top-k context chunks
            raw_results = self.vector_store.search(question_clean, top_k=top_k)
            logger.info("Raw vector search returned %d candidates", len(raw_results))

            # 2. Filter results by minimum relevance score threshold
            filtered_results = [res for res in raw_results if res.relevance >= effective_threshold]
            logger.info("Filtered search returned %d candidates passing threshold %.2f", len(filtered_results), effective_threshold)

            # 3. Grounded fallback response if no results pass threshold
            if not filtered_results:
                logger.info("No candidates passed relevance threshold %.2f. Returning fallback response.", effective_threshold)
                return {
                    "answer": FALLBACK_RESPONSE_TEXT,
                    "sources": [],
                }

            # 4. Build system/user prompt with filtered results only
            prompt = PromptBuilder.build_prompt(question_clean, filtered_results)

            # 5. Generate LLM response using filtered results
            answer = self.llm_provider.generate_response(prompt, filtered_results)

            # 6. Format sources metadata using filtered results only
            sources = []
            for res in filtered_results:
                sources.append({
                    "document": res.document_name,
                    "page": res.page_number,
                    "relevance": round(float(res.relevance), 2),
                })

            logger.info("Successfully synthesized answer with %d source citation(s)", len(sources))
            return {
                "answer": answer,
                "sources": sources,
            }
        except Exception as e:
            logger.exception("Unexpected error in RAGPipeline.ask for query '%s': %s", question_clean, str(e))
            raise


