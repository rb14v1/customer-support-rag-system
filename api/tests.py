"""
Integration tests for Django REST API endpoints.
"""

# pyrefly: ignore [missing-import]
from rest_framework.test import APITestCase
# pyrefly: ignore [missing-import]
from rest_framework import status
# pyrefly: ignore [missing-import]
from django.urls import reverse
from django.test import override_settings
from rag.retrieve import ProviderRegistry
from rag.rag import FALLBACK_RESPONSE_TEXT


class APIEndpointsTestCase(APITestCase):
    """Test REST API endpoints: health, ingest, documents, and chat."""

    def setUp(self):
        ProviderRegistry.reset_defaults()

    def tearDown(self):
        ProviderRegistry.reset_defaults()

    def test_health_endpoint(self):
        url = reverse('api-health')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'healthy')
        self.assertIn('documents_indexed', response.data)
        self.assertIn('chunks_indexed', response.data)
        self.assertIn('vector_store_provider', response.data)

    def test_documents_endpoint(self):
        url = reverse('api-documents')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_documents', response.data)
        self.assertIn('total_chunks', response.data)
        self.assertIn('documents', response.data)

    def test_ingest_endpoint(self):
        url = reverse('api-ingest')
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertGreater(response.data['documents_processed'], 0)
        self.assertGreater(response.data['total_chunks'], 0)

    def test_chat_endpoint(self):
        url = reverse('api-chat')
        payload = {
            "question": "What is the return policy?"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('answer', response.data)
        self.assertIn('sources', response.data)
        self.assertIsInstance(response.data['sources'], list)
        self.assertGreater(len(response.data['sources']), 0)
        self.assertEqual(response.data['sources'][0]['document'], 'returns_refunds.pdf')

    def test_chat_endpoint_valid_warranty_question(self):
        url = reverse('api-chat')
        payload = {
            "question": "What does the warranty cover?"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('answer', response.data)
        self.assertGreater(len(response.data['sources']), 0)
        self.assertEqual(response.data['sources'][0]['document'], 'warranty_policy.pdf')

    def test_chat_endpoint_out_of_domain_question(self):
        url = reverse('api-chat')
        for q in ["Who won the 1st cricket world cup?", "Who won the first cricket world cup?"]:
            payload = {"question": q}
            response = self.client.post(url, payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['sources'], [], f"Expected empty sources for: {q}")
            self.assertEqual(response.data['answer'], FALLBACK_RESPONSE_TEXT)

    @override_settings(RAG_MIN_RELEVANCE_SCORE=0.99)
    def test_chat_endpoint_threshold_override(self):
        url = reverse('api-chat')
        payload = {
            "question": "What is the return policy?"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sources'], [])
        self.assertEqual(response.data['answer'], FALLBACK_RESPONSE_TEXT)

    def test_chat_endpoint_empty_question_handling(self):
        url = reverse('api-chat')
        payload = {
            "question": ""
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_ingest_endpoint_nonexistent_directory(self):
        url = reverse('api-ingest')
        payload = {"data_dir": "non_existent_folder_xyz_123"}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
