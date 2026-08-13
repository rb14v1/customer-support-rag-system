"""
Serializers for Django REST API endpoints.
"""

from rest_framework import serializers


class ConversationMessageSerializer(serializers.Serializer):
    role = serializers.CharField(
        help_text="Message role: 'user' or 'assistant'."
    )
    content = serializers.CharField(
        allow_blank=True,
        help_text="Message content text."
    )


class ChatQuerySerializer(serializers.Serializer):
    question = serializers.CharField(
        required=True,
        allow_blank=False,
        help_text="Customer support query or question text."
    )
    top_k = serializers.IntegerField(
        required=False,
        default=3,
        min_value=1,
        max_value=10,
        help_text="Number of top context chunks to retrieve."
    )
    conversation_history = ConversationMessageSerializer(
        many=True,
        required=False,
        default=[],
        help_text="Previous conversation messages for multi-turn context."
    )


class SourceCitationSerializer(serializers.Serializer):
    document = serializers.CharField()
    page = serializers.IntegerField()
    relevance = serializers.FloatField()
    chunk_id = serializers.CharField(required=False, allow_blank=True, default="")
    text = serializers.CharField(required=False, allow_blank=True, default="")
    url = serializers.CharField(required=False, allow_blank=True, default="")
    title = serializers.CharField(required=False, allow_blank=True, default="")


class ChatResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    sources = SourceCitationSerializer(many=True)


class IngestRequestSerializer(serializers.Serializer):
    data_dir = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional custom directory path containing PDF documents to ingest."
    )


class IngestResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    documents_processed = serializers.IntegerField()
    total_chunks = serializers.IntegerField()
    documents = serializers.ListField(child=serializers.CharField())


class DocumentStatsSerializer(serializers.Serializer):
    total_documents = serializers.IntegerField()
    total_chunks = serializers.IntegerField()
    documents = serializers.ListField(child=serializers.CharField())


class HealthCheckSerializer(serializers.Serializer):
    status = serializers.CharField()
    documents_indexed = serializers.IntegerField()
    chunks_indexed = serializers.IntegerField()
    vector_store_provider = serializers.CharField()
