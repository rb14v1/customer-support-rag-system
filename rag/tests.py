"""
Unit tests for RAG package modules: ingest, retrieve, rag, and DI registry.
"""

from pathlib import Path
from django.test import TestCase, override_settings

from rag.ingest import PDFExtractor, DocumentChunker, IngestionPipeline
from rag.retrieve import (
    AbstractEmbeddingProvider,
    AbstractVectorStoreProvider,
    AbstractLLMProvider,
    DocumentChunk,
    SearchResult,
    MockEmbeddingProvider,
    MockVectorStoreProvider,
    ProviderRegistry,
)
from rag.rag import PromptBuilder, MockLLMProvider, RAGPipeline, FALLBACK_RESPONSE_TEXT


class RAGIngestTestCase(TestCase):
    """Test PDF extraction and chunking functionality."""

    def setUp(self):
        self.chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
        self.sample_pdf = Path(__file__).resolve().parent.parent / "data" / "faq.pdf"

    def test_pdf_extraction(self):
        if self.sample_pdf.is_file():
            pages = PDFExtractor.extract_pages(self.sample_pdf)
            self.assertIsInstance(pages, list)
            self.assertGreater(len(pages), 0)
            self.assertIn("page_number", pages[0])
            self.assertIn("text", pages[0])

    def test_chunker(self):
        text = "This is a sample sentence. " * 10
        chunks = self.chunker.chunk_page(
            document_name="test.pdf",
            page_number=1,
            page_text=text,
        )
        self.assertGreater(len(chunks), 0)
        self.assertEqual(chunks[0].document_name, "test.pdf")
        self.assertEqual(chunks[0].page_number, 1)
        self.assertIsNotNone(chunks[0].chunk_id)


class RAGRetrieveTestCase(TestCase):
    """Test retrieval providers, vector similarity search, and DI registry."""

    def setUp(self):
        ProviderRegistry.reset_defaults()
        self.vector_store = MockVectorStoreProvider()

    def tearDown(self):
        ProviderRegistry.reset_defaults()

    def test_embedding_provider(self):
        provider = MockEmbeddingProvider(dim=64)
        emb = provider.embed_text("test question")
        self.assertEqual(len(emb), 64)
        batch = provider.embed_batch(["one", "two"])
        self.assertEqual(len(batch), 2)

    def test_vector_store_indexing_and_search(self):
        chunks = [
            DocumentChunk(
                chunk_id="c1",
                text="Return policy allows refunds within 30 days.",
                document_name="returns_refunds.pdf",
                page_number=1,
            ),
            DocumentChunk(
                chunk_id="c2",
                text="Shipping takes 3-5 business days for standard delivery.",
                document_name="shipping_policy.pdf",
                page_number=2,
            ),
        ]
        indexed_count = self.vector_store.index_chunks(chunks)
        self.assertEqual(indexed_count, 2)

        results = self.vector_store.search("refund return policy", top_k=2)
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], SearchResult)
        self.assertEqual(results[0].document_name, "returns_refunds.pdf")

    def test_provider_registry_injection(self):
        class DummyEmbeddingProvider(AbstractEmbeddingProvider):
            def embed_text(self, text: str):
                return [0.5, 0.5]
            def embed_batch(self, texts):
                return [[0.5, 0.5] for _ in texts]

        dummy = DummyEmbeddingProvider()
        ProviderRegistry.set_embedding_provider(dummy)
        self.assertIs(ProviderRegistry.get_embedding_provider(), dummy)

    def test_repeated_indexing_idempotency(self):
        chunks = [
            DocumentChunk(
                chunk_id="c1",
                text="Return policy allows refunds within 30 days.",
                document_name="returns_refunds.pdf",
                page_number=1,
            ),
        ]
        self.vector_store.index_chunks(chunks)
        self.assertEqual(len(self.vector_store.chunks), 1)

        # Indexing identical chunk again should update, not duplicate
        self.vector_store.index_chunks(chunks)
        self.assertEqual(len(self.vector_store.chunks), 1)
        stats = self.vector_store.get_document_stats()
        self.assertEqual(stats["total_chunks"], 1)
        self.assertEqual(stats["total_documents"], 1)


class RAGPipelineTestCase(TestCase):
    """Test prompt building and RAG pipeline answer generation."""

    def setUp(self):
        ProviderRegistry.reset_defaults()
        self.vector_store = ProviderRegistry.get_vector_store_provider()
        self.vector_store.index_chunks([
            DocumentChunk(
                chunk_id="faq1",
                text="To reset your password, click on Forgot Password at login screen.",
                document_name="faq.pdf",
                page_number=3,
            )
        ])

    def tearDown(self):
        ProviderRegistry.reset_defaults()

    def test_prompt_builder(self):
        results = [
            SearchResult(
                chunk_id="faq1",
                text="Reset password instructions",
                document_name="faq.pdf",
                page_number=3,
                relevance=0.88,
            )
        ]
        prompt = PromptBuilder.build_prompt("How to reset password?", results)
        self.assertIn("faq.pdf", prompt)
        self.assertIn("Page 3", prompt)

    def test_rag_pipeline_ask(self):
        pipeline = RAGPipeline(vector_store_provider=self.vector_store)
        res = pipeline.ask("How to reset password?")

        self.assertIn("answer", res)
        self.assertIn("sources", res)
        self.assertIsInstance(res["sources"], list)
        self.assertGreater(len(res["sources"]), 0)
        self.assertEqual(res["sources"][0]["document"], "faq.pdf")
        self.assertEqual(res["sources"][0]["page"], 3)
        self.assertIn("relevance", res["sources"][0])

    def test_retrieval_ranking_quality(self):
        data_dir = Path(__file__).resolve().parent.parent / "data"
        if data_dir.is_dir():
            pipeline = IngestionPipeline()
            pipeline.ingest_directory(data_dir)
            rag = RAGPipeline()

            test_cases = [
                ("What is the return policy?", "returns_refunds.pdf"),
                ("How long does shipping take?", "shipping_policy.pdf"),
                ("What does the warranty cover?", "warranty_policy.pdf"),
                ("How do I change my account information?", "account_management.pdf"),
            ]

            for question, expected_doc in test_cases:
                result = rag.ask(question=question, top_k=1)
                self.assertTrue(len(result["sources"]) > 0, f"No sources for query: {question}")
                top_doc = result["sources"][0]["document"]
                self.assertEqual(
                    top_doc, expected_doc,
                    f"Query '{question}' retrieved '{top_doc}' instead of expected '{expected_doc}'"
                )

    def test_out_of_domain_query_rejection(self):
        data_dir = Path(__file__).resolve().parent.parent / "data"
        if data_dir.is_dir():
            pipeline = IngestionPipeline()
            pipeline.ingest_directory(data_dir)
            rag = RAGPipeline()

            # Out-of-domain questions
            for q in ["Who won the 1st cricket world cup?", "Who won the first cricket world cup?"]:
                result = rag.ask(q)
                self.assertEqual(result["sources"], [], f"Expected empty sources for out-of-domain query: {q}")
                self.assertEqual(result["answer"], FALLBACK_RESPONSE_TEXT)

    @override_settings(RAG_MIN_RELEVANCE_SCORE=0.95)
    def test_dynamic_threshold_override(self):
        data_dir = Path(__file__).resolve().parent.parent / "data"
        if data_dir.is_dir():
            pipeline = IngestionPipeline()
            pipeline.ingest_directory(data_dir)
            rag = RAGPipeline()

            # With threshold 0.95, even valid questions with relevance < 0.95 are filtered out
            result = rag.ask("What is the return policy?")
            self.assertEqual(result["sources"], [])
            self.assertEqual(result["answer"], FALLBACK_RESPONSE_TEXT)

    def test_provider_registry_type_checking(self):
        with self.assertRaises(TypeError):
            ProviderRegistry.set_embedding_provider("invalid_provider")
        with self.assertRaises(TypeError):
            ProviderRegistry.set_vector_store_provider("invalid_provider")
        with self.assertRaises(TypeError):
            ProviderRegistry.set_llm_provider("invalid_provider")

    def test_pdf_extractor_non_existent_file(self):
        with self.assertRaises(FileNotFoundError):
            PDFExtractor.extract_pages(Path("non_existent_file.pdf"))

    def test_chunker_invalid_parameters(self):
        with self.assertRaises(ValueError):
            DocumentChunker(chunk_size=0)
        with self.assertRaises(ValueError):
            DocumentChunker(chunk_size=100, chunk_overlap=150)
